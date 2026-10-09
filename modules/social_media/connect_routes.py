"""Connecting Instagram, and the webhook Meta calls. The two webhook endpoints are public on purpose (Meta calls them), so
they trust nothing: the verification token and every payload's signature are checked before anything is read."""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.exceptions import ValidationError
from app.core.limiter import limiter
from app.core.logging_config import get_logger
from app.db.session import get_db
from modules.authentication.models import User, UserStatus
from modules.authorization.dependencies import require_permissions
from modules.authorization.repository import AuthorizationRepository
from modules.social_media import oauth
from modules.social_media.connection import ConnectionService
from modules.social_media.models import SocialAccount, WebhookEvent
from modules.social_media.oauth import OAuthError
from modules.users.dependencies import get_current_user_organization_id

logger = get_logger(__name__)
router = APIRouter()

CONNECT = "social_media.connect"
MAX_WEBHOOK_BYTES = 1_000_000


class StartResponse(BaseModel):
    url: str


class RecheckResponse(BaseModel):
    capabilities: dict


class MessageResponse(BaseModel):
    message: str


def _back(ok: bool, reason: str | None = None) -> RedirectResponse:
    target = f"{app_settings.FRONTEND_URL.rstrip('/')}/social-media?tab=settings&connect={'ok' if ok else 'error'}"
    if reason:
        target += f"&reason={reason}"
    return RedirectResponse(target, status_code=303)


# ---------------- connecting ----------------


@router.post("/connect/start", response_model=StartResponse)
async def start_connection(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(CONNECT)),
    db: AsyncSession = Depends(get_db),
):
    """The Instagram address to send the person to. Only someone with social_media.connect can start it."""
    url = await ConnectionService(db).start(organization_id, user.id)
    await db.commit()
    return StartResponse(url=url)


@router.get("/connect/callback")
async def connection_callback(
    code: str | None = Query(default=None, max_length=1000),
    state: str | None = Query(default=None, max_length=2000),
    error: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    """Where Instagram sends the person back. It checks the signed, one-use state, finishes the connection on the server and
    sends the browser back to the Settings page. It never shows tokens or provider text."""
    if not state:
        return _back(False, "state")
    service = ConnectionService(db)
    try:
        organization_id, user_id = await service.verify_state(state)
        await db.commit()  # the link is spent, whatever happens next
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        allowed = user is not None and user.status == UserStatus.ACTIVE
        if allowed and not user.is_superuser:
            allowed = CONNECT in await AuthorizationRepository(db).get_permission_codes_for_user(user.id)
        if not allowed:
            raise OAuthError("permission", "The person who started this connection can no longer connect accounts.")
        if error or not code:
            raise OAuthError("denied", "The connection was cancelled on Instagram.")
        await service.complete(organization_id, code)
        await db.commit()
        return _back(True)
    except OAuthError as exc:
        await db.rollback()
        logger.info("social_connect_failed", reason=exc.code)
        return _back(False, exc.code)
    except ValidationError:
        await db.rollback()
        return _back(False, "account_type")


@router.post("/connect/disconnect", response_model=MessageResponse)
async def disconnect(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(CONNECT)),
    db: AsyncSession = Depends(get_db),
):
    """Forget the access token (and stop the webhook). Posts, comments and history stay."""
    await ConnectionService(db).disconnect(organization_id)
    await db.commit()
    return MessageResponse(message="Disconnected. The access token was deleted from this server.")


@router.post("/connect/recheck", response_model=RecheckResponse)
async def recheck(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(CONNECT)),
    db: AsyncSession = Depends(get_db),
):
    """Ask Instagram again what this account can do (for example after the app's permissions changed)."""
    service = ConnectionService(db)
    account = await service.get(organization_id)
    if account is None or not account.token_encrypted:
        raise ValidationError("Instagram isn't connected.")
    caps = await service.recheck(account)
    await db.commit()
    return RecheckResponse(capabilities=caps)


@router.post("/connect/refresh-token", response_model=MessageResponse)
async def refresh_token(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(CONNECT)),
    db: AsyncSession = Depends(get_db),
):
    """Refresh the access token now (it is also refreshed automatically before it expires)."""
    service = ConnectionService(db)
    account = await service.get(organization_id)
    if account is None or not account.token_encrypted:
        raise ValidationError("Instagram isn't connected.")
    if not await service.refresh_token(account):
        await db.commit()
        raise ValidationError(account.last_error or "The token couldn't be refreshed. Reconnect the account.")
    await db.commit()
    return MessageResponse(message="The access token was refreshed.")


# ---------------- the webhook ----------------


@router.get("/webhooks/instagram", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str = Query(alias="hub.mode", default=""),
    challenge: str = Query(alias="hub.challenge", default="", max_length=200),
    verify_token: str = Query(alias="hub.verify_token", default="", max_length=500),
):
    """Meta's one-off check that this address is ours: it must send back the token we configured."""
    expected = app_settings.INSTAGRAM_WEBHOOK_VERIFY_TOKEN
    if not expected or mode != "subscribe" or not hmac.compare_digest(verify_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Verification failed.")
    return PlainTextResponse(challenge)


def signature_ok(raw: bytes, header: str | None) -> bool:
    secret = app_settings.INSTAGRAM_APP_SECRET
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def extract_events(payload: object) -> list[tuple[str, str, str | None, str]]:
    """(account id, field, object id, canonical text) for every notification in a payload. Read defensively: Meta's docs
    don't spell out every nested shape, so anything unrecognised is skipped, never trusted."""
    events: list[tuple[str, str, str | None, str]] = []
    if not isinstance(payload, dict) or not isinstance(payload.get("entry"), list):
        return events
    for entry in payload["entry"]:
        if not isinstance(entry, dict) or entry.get("id") is None:
            continue
        entry_id = str(entry["id"])[:100]
        for change in entry.get("changes") or []:
            if isinstance(change, dict) and change.get("field"):
                value = change.get("value") if isinstance(change.get("value"), dict) else {}
                object_id = value.get("id") or value.get("comment_id") or value.get("media_id")
                text = json.dumps({"e": entry_id, "f": change["field"], "v": value}, sort_keys=True, default=str)
                events.append((entry_id, str(change["field"])[:60], str(object_id)[:200] if object_id else None, text))
        for message in entry.get("messaging") or []:
            if not isinstance(message, dict):
                continue
            kind = next((k for k in ("message", "read", "postback", "reaction", "referral") if k in message), "messages")
            field = "messages" if kind == "message" else f"messaging_{kind}"
            inner = message.get("message") if isinstance(message.get("message"), dict) else {}
            object_id = inner.get("mid")
            events.append((entry_id, field, str(object_id)[:200] if object_id else None, json.dumps({"e": entry_id, "m": message}, sort_keys=True, default=str)))
        for field in entry.get("changed_fields") or []:
            events.append((entry_id, str(field)[:60], None, json.dumps({"e": entry_id, "f": field, "t": entry.get("time")}, sort_keys=True, default=str)))
    return events


@router.post("/webhooks/instagram")
@limiter.limit("600/minute")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Meta's notifications (a new comment, a new message). The signature is checked first; a retried notification is
    recognised and ignored. Only ids are kept. Acting on them (reading the new comment or message from the API) happens in
    the background, never here."""
    if not app_settings.INSTAGRAM_APP_SECRET:
        raise HTTPException(status_code=503, detail="Webhooks aren't configured on this server.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large.")
    raw = await request.body()
    if len(raw) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large.")
    if not signature_ok(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=403, detail="Invalid signature.")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Not JSON.") from None

    received = new = 0
    touched: set[uuid.UUID] = set()
    for entry_id, field, object_id, text in extract_events(payload):
        received += 1
        digest = hashlib.sha256(text.encode()).hexdigest()
        if (await db.execute(select(WebhookEvent.id).where(WebhookEvent.event_hash == digest))).first():
            continue  # Meta retries; each notification is handled once
        account = (await db.execute(select(SocialAccount).where(SocialAccount.external_account_id == entry_id).limit(1))).scalar_one_or_none()
        db.add(WebhookEvent(organization_id=account.organization_id if account else None, event_hash=digest, entry_id=entry_id, field=field, object_id=object_id))
        await db.flush()
        new += 1
        if account is not None:
            touched.add(account.id)
    await db.commit()
    for account_id in touched:
        _wake(account_id)
    return {"received": received, "new": new}


def _wake(account_id: uuid.UUID) -> None:
    """Hook for the background reader of new comments and messages (added with the inbox). Does nothing yet."""
    logger.info("social_webhook_event", account_id=str(account_id), at=datetime.now(timezone.utc).isoformat())
