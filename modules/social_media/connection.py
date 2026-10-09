"""
The Instagram connection: start, complete, check, refresh and disconnect.

A connection is one Instagram professional account per organisation. Its access token is stored encrypted (token_crypto) and
never leaves the server. After connecting, what the account can really do is *probed* (can we read the publishing quota,
the media list, the conversations?) and recorded per feature, so the Settings page can say "available", "unavailable" or
"needs Meta app review" from what Instagram answered instead of what we hoped.
"""

import hmac
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.core.logging_config import get_logger
from modules.social_media import instagram, oauth
from modules.social_media.instagram import InstagramError
from modules.social_media.models import SocialAccount, SocialSettings
from modules.social_media.oauth import OAuthError
from modules.social_media.service import SettingsService
from modules.social_media.token_crypto import TokenUnreadable, decrypt_token, encrypt_token

logger = get_logger(__name__)

EXPIRING_WITHIN = timedelta(days=14)  # shown as "expiring" and warned about
REFRESH_WITHIN = timedelta(days=20)  # the daily job refreshes a token this close to its end
MIN_TOKEN_AGE = timedelta(hours=24)  # Instagram only refreshes tokens at least a day old
WEBHOOK_FIELDS = {"manage_comments": "comments", "manage_messages": "messages"}
PREFIX = "instagram_business_"


def notify_account_problem(account: SocialAccount, problem: str, detail: str) -> None:
    """Email the people who run the page about the connection. Never raises."""
    try:
        from modules.social_media.tasks import enqueue_account_problem_email

        enqueue_account_problem_email(account.id, problem, detail)
    except Exception:  # noqa: BLE001 - a notification problem must not hide the real one
        logger.warning("social_account_notify_failed", account_id=str(account.id), exc_info=True)


def computed_status(account: SocialAccount | None, now: datetime) -> str:
    """The account's real state now, from its token's expiry, whatever was stored last."""
    if account is None or not account.token_encrypted:
        return "not_connected"
    if account.status in ("revoked", "error", "not_connected"):
        return account.status
    if account.token_expires_at and account.token_expires_at <= now:
        return "expired"
    if account.token_expires_at and account.token_expires_at - now <= EXPIRING_WITHIN:
        return "expiring"
    return "connected"


def days_left(account: SocialAccount | None, now: datetime) -> int | None:
    if account is None or account.token_expires_at is None:
        return None
    return max(0, (account.token_expires_at - now).days)


class ConnectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, organization_id: uuid.UUID) -> SocialAccount | None:
        return (
            await self.db.execute(
                select(SocialAccount).where(SocialAccount.organization_id == organization_id, SocialAccount.platform == "instagram").order_by(SocialAccount.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()

    # ---------------- start ----------------

    async def start(self, organization_id: uuid.UUID, user_id: uuid.UUID, now: datetime | None = None) -> str:
        """The address to send the person to. Remembers a one-use nonce so only this attempt can complete."""
        now = now or datetime.now(timezone.utc)
        if not oauth.configured():
            raise ValidationError(
                "The Meta app isn't set up on this server yet. Create it as described under Settings, then set INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET."
            )
        settings = await SettingsService(self.db).get(organization_id)
        nonce = oauth.new_nonce()
        settings.connect_state = {"nonce": nonce, "user_id": str(user_id), "expires": (now + oauth.STATE_LIFETIME).isoformat()}
        await self.db.flush()
        return oauth.authorize_url(oauth.make_state(str(organization_id), str(user_id), nonce, now))

    # ---------------- complete ----------------

    async def verify_state(self, state: str, now: datetime | None = None) -> tuple[uuid.UUID, uuid.UUID]:
        """(organisation, user) the redirect belongs to; the nonce is used up, so a link works once."""
        now = now or datetime.now(timezone.utc)
        claims = oauth.read_state(state)
        try:
            organization_id, user_id = uuid.UUID(claims["org"]), uuid.UUID(claims["user"])
        except (KeyError, ValueError):
            raise OAuthError("state", "This connection link isn't valid. Start the connection again.") from None
        # Never create anything for an organisation named in a link: it must already exist and have started a connection.
        settings = (await self.db.execute(select(SocialSettings).where(SocialSettings.organization_id == organization_id))).scalar_one_or_none()
        if settings is None:
            raise OAuthError("state", "This connection link isn't valid. Start the connection again.")
        pending = settings.connect_state or {}
        expires = pending.get("expires")
        valid = (
            pending.get("nonce")
            and hmac.compare_digest(str(pending["nonce"]), str(claims.get("nonce", "")))
            and pending.get("user_id") == str(user_id)
            and expires
            and datetime.fromisoformat(expires) > now
        )
        settings.connect_state = {}
        await self.db.flush()
        if not valid:
            raise OAuthError("state", "This connection link was already used or has expired. Start the connection again.")
        return organization_id, user_id

    async def complete(self, organization_id: uuid.UUID, code: str, now: datetime | None = None) -> SocialAccount:
        """Exchange the code, store the long-lived token encrypted, and find out what the account can do."""
        now = now or datetime.now(timezone.utc)
        short_token, user_id, granted = await oauth.exchange_code(code)
        token, expires_in = await oauth.long_lived(short_token)
        client = instagram.get_instagram_client(user_id, token)
        try:
            profile = await client.me()
        except InstagramError as exc:
            raise OAuthError("profile", f"The account's details couldn't be read: {exc.message}") from None
        oauth.check_professional(profile.get("account_type"))
        ig_id = str(profile.get("user_id") or profile.get("id") or user_id)
        if ig_id != user_id:
            client = instagram.get_instagram_client(ig_id, token)

        account = await self.get(organization_id)
        if account is None:
            account = SocialAccount(organization_id=organization_id, platform="instagram", external_account_id=ig_id)
            self.db.add(account)
        elif account.external_account_id != ig_id:
            account.external_account_id = ig_id  # a different Instagram account: nothing read from the old one carries over
            account.sync_state = {}
        account.username = str(profile.get("username") or "")[:100] or None
        account.account_type = str(profile.get("account_type") or "")[:30] or None
        account.token_encrypted = encrypt_token(token)
        account.token_expires_at = now + timedelta(seconds=expires_in)
        account.connected_at = now
        account.status = "connected"
        account.last_error = None
        account.scopes = sorted(granted)
        account.sync_state = {**(account.sync_state or {}), "token": {"refreshed_at": now.isoformat()}}
        await self.db.flush()
        account.capabilities = await self._probe(client, set(granted), account)
        await self.db.flush()
        return account

    # ---------------- what can it really do? ----------------

    async def _probe(self, client: instagram.InstagramClient, granted: set[str], account: SocialAccount) -> dict:
        def has(scope: str) -> bool:
            return f"{PREFIX}{scope}" in granted

        async def probe(call, permission_state: str = "unavailable") -> str:
            try:
                await call()
                return "available"
            except InstagramError as exc:
                if exc.kind == "token":
                    raise OAuthError("token", exc.message) from None
                return "unknown" if exc.kind in ("transient", "ambiguous") else permission_state

        caps: dict[str, str] = {}
        caps["publish"] = await probe(client.publishing_limit) if has("content_publish") else "unavailable"
        caps["comments"] = await probe(lambda: client.recent_media(1)) if has("manage_comments") else "unavailable"
        # a missing permission on a scope we were granted usually means the feature needs Meta's app review
        caps["messages"] = await probe(lambda: client.list_conversations(1), "needs_app_review") if has("manage_messages") else "unavailable"
        caps["insights"] = "available" if has("manage_insights") else "unavailable"
        fields = [field for scope, field in WEBHOOK_FIELDS.items() if has(scope)]
        caps["webhooks"] = "not_subscribed"
        if fields and oauth.configured():
            try:
                caps["webhooks"] = "subscribed" if await client.subscribe_webhooks(fields) else "not_subscribed"
            except InstagramError as exc:
                if exc.kind == "token":
                    raise OAuthError("token", exc.message) from None
                caps["webhooks"] = "error"
        return caps

    async def recheck(self, account: SocialAccount) -> dict:
        """Ask Instagram again what the connected account can do (after the app's permissions changed, say)."""
        client = await self._client(account)
        try:
            account.capabilities = await self._probe(client, set(account.scopes or []), account)
        except OAuthError as exc:
            await self._mark_failed(account, exc.message, datetime.now(timezone.utc))
            raise ValidationError(exc.message) from None
        await self.db.flush()
        return account.capabilities

    # ---------------- disconnect ----------------

    async def disconnect(self, organization_id: uuid.UUID) -> None:
        account = await self.get(organization_id)
        if account is None or not account.token_encrypted:
            raise ConflictError("Instagram isn't connected.")
        try:
            await (await self._client(account)).unsubscribe_webhooks()
        except (InstagramError, TokenUnreadable):
            logger.info("social_unsubscribe_skipped", account_id=str(account.id))
        account.token_encrypted = None
        account.token_expires_at = None
        account.status = "not_connected"
        account.capabilities = {}
        account.sync_state = {}
        account.last_error = None
        await self.db.flush()

    # ---------------- keeping the token alive ----------------

    async def _client(self, account: SocialAccount) -> instagram.InstagramClient:
        if not account.token_encrypted:
            raise ConflictError("Instagram isn't connected.")
        return instagram.get_instagram_client(account.external_account_id, decrypt_token(account.token_encrypted))

    async def _mark_failed(self, account: SocialAccount, message: str, now: datetime) -> None:
        expired = bool(account.token_expires_at and account.token_expires_at <= now)
        account.status = "expired" if expired else "revoked"
        account.last_error = message[:500]
        await self.db.flush()

    async def refresh_token(self, account: SocialAccount, now: datetime | None = None) -> bool:
        """Swap the token for a fresh 60-day one. False when it couldn't (the reason is recorded on the account)."""
        now = now or datetime.now(timezone.utc)
        try:
            current = decrypt_token(account.token_encrypted or "")
            token, expires_in = await oauth.refresh(current)
        except TokenUnreadable as exc:
            await self._mark_failed(account, str(exc), now)
            return False
        except OAuthError as exc:
            if exc.code == "network":
                account.last_error = exc.message
                await self.db.flush()
                return False
            await self._mark_failed(account, exc.message, now)
            return False
        account.token_encrypted = encrypt_token(token)
        account.token_expires_at = now + timedelta(seconds=expires_in)
        account.status = "connected"
        account.last_error = None
        account.sync_state = {**(account.sync_state or {}), "token": {"refreshed_at": now.isoformat()}}
        await self.db.flush()
        return True

    async def refresh_due(self, now: datetime | None = None) -> dict[str, int]:
        """The daily job: refresh tokens that are within 20 days of expiry; warn when one can't be kept alive."""
        now = now or datetime.now(timezone.utc)
        result = {"refreshed": 0, "failed": 0, "skipped": 0}
        rows = await self.db.execute(
            select(SocialAccount).where(
                SocialAccount.token_encrypted.is_not(None),
                SocialAccount.status.in_(("connected", "expiring")),
                SocialAccount.token_expires_at <= now + REFRESH_WITHIN,
            )
        )
        for account in rows.scalars().all():
            last = _parse((account.sync_state or {}).get("token", {}).get("refreshed_at")) or account.connected_at
            if last and now - last < MIN_TOKEN_AGE:
                result["skipped"] += 1
                continue
            if await self.refresh_token(account, now):
                result["refreshed"] += 1
                continue
            result["failed"] += 1
            remaining = account.token_expires_at - now if account.token_expires_at else timedelta(0)
            if account.status in ("expired", "revoked") or remaining <= timedelta(days=7):
                notify_account_problem(
                    account,
                    "The Instagram connection needs attention",
                    f"{account.last_error or 'The access token could not be refreshed.'} Reconnect the account in Settings before it stops working.",
                )
        return result


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
