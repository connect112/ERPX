"""
Replies to comments and direct messages: ONLY ever sent because a person pressed Send.

This is the one place in the module that sends anything to an audience. Nothing here is reachable from a sync, a webhook, a
background task, a classifier or an AI suggestion: the only callers are the two explicit reply routes (and the two ways a
person settles an unclear one). The rules that protect against mistakes:

- the reply's record (who, exactly what text, where it came from, what was acknowledged) is written and committed BEFORE the
  send is attempted, so there is always an audit trail, even if the server dies mid-send
- the browser makes one request id per reply; sending the same id again returns the first result and never sends twice
  (a double click, a retried request). An identical message to the same target within five minutes is refused as a duplicate
- the status shown is the truth: "sent" only after Instagram confirmed; "failed" only when it certainly was not sent; an
  unclear answer (timeout, dropped connection) is "unknown", never retried automatically, and checked against Instagram on request
- sensitive items (complaints, refunds, legal, security incidents) need the person's explicit acknowledgement
- a direct message can only be sent within 24 hours of the person's last message; Instagram can't start a conversation
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.social_media import instagram
from modules.social_media.connection import ConnectionService, computed_status
from modules.social_media.inbox import WINDOW, InboxService, parse_time
from modules.social_media.instagram import InstagramError
from modules.social_media.models import IgComment, IgConversation, IgMessage, SocialAccount, SocialReply
from modules.social_media.token_crypto import TokenUnreadable, decrypt_token

logger = get_logger(__name__)

COMMENT_LIMIT = 2200  # Instagram's comment length limit
DM_LIMIT_BYTES = 1000  # Instagram's text message limit
DUPLICATE_WINDOW = timedelta(minutes=5)
CHECK_SLACK = timedelta(minutes=2)
SOURCES = ("typed", "suggestion_edited", "suggestion_unchanged")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_message(text: str) -> str:
    cleaned = _CONTROL.sub("", text.replace("\r\n", "\n").replace("\r", "\n")).strip()
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


class ReplyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.connections = ConnectionService(db)

    # ---------------- checks shared by both kinds ----------------

    async def _account(self, organization_id: uuid.UUID, capability: str, now: datetime) -> SocialAccount:
        account = await self.connections.get(organization_id)
        if account is None or computed_status(account, now) not in ("connected", "expiring"):
            raise ValidationError("Instagram isn't connected, so nothing can be sent. Reconnect it in Settings.")
        state = (account.capabilities or {}).get(capability)
        if state == "unavailable":
            raise ValidationError("This Instagram connection wasn't granted permission for this. Reconnect and allow it (Settings).")
        if state == "needs_app_review":
            raise ValidationError("Instagram hasn't yet allowed this app to do this. It needs Meta's app review (see Settings, Check what it can do).")
        return account

    async def _existing(self, organization_id: uuid.UUID, request_id: str) -> SocialReply | None:
        return (await self.db.execute(select(SocialReply).where(SocialReply.organization_id == organization_id, SocialReply.request_id == request_id))).scalar_one_or_none()

    async def _duplicate(self, organization_id: uuid.UUID, kind: str, target: str, message: str, now: datetime) -> bool:
        rows = await self.db.execute(
            select(SocialReply.id).where(
                SocialReply.organization_id == organization_id,
                SocialReply.kind == kind,
                SocialReply.target_external_id == target,
                SocialReply.message == message,
                SocialReply.status.in_(("pending", "sent", "unknown")),
                SocialReply.created_at >= now - DUPLICATE_WINDOW,
            ).limit(1)
        )
        return rows.first() is not None

    @staticmethod
    def _source(message: str, suggestion: str | None, from_suggestion: bool) -> str:
        if suggestion and message.strip() == suggestion.strip():
            return "suggestion_unchanged"
        return "suggestion_edited" if from_suggestion else "typed"

    async def _client(self, account: SocialAccount) -> instagram.InstagramClient:
        return instagram.get_instagram_client(account.external_account_id, decrypt_token(account.token_encrypted or ""))

    # ---------------- comments ----------------

    async def send_comment(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        comment: IgComment,
        message: str,
        request_id: str,
        from_suggestion: bool = False,
        acknowledge_sensitive: bool = False,
        now: datetime | None = None,
    ) -> SocialReply:
        now = now or datetime.now(timezone.utc)
        if (earlier := await self._existing(organization_id, request_id)) is not None:
            return earlier
        text = clean_message(message)
        if not text:
            raise ValidationError("Write a reply first.")
        if len(text) > COMMENT_LIMIT:
            raise ValidationError(f"A comment reply can be at most {COMMENT_LIMIT} characters (this one is {len(text)}).")
        if comment.is_own or comment.parent_external_id:
            raise ValidationError("Reply to the original comment, not to a reply.")
        if comment.needs_care and not acknowledge_sensitive:
            raise ValidationError(f"{comment.care_reason or 'This comment needs careful handling.'} Confirm that you are handling it personally.")
        account = await self._account(organization_id, "comments", now)
        if await self._duplicate(organization_id, "comment", comment.external_id, text, now):
            raise ValidationError("This exact reply was already sent to this comment a moment ago.")
        reply = SocialReply(
            organization_id=organization_id, user_id=user_id, request_id=request_id, kind="comment", comment_id=comment.id,
            target_external_id=comment.external_id, message=text, source=self._source(text, comment.suggested_reply, from_suggestion),
            acknowledged_sensitive=acknowledge_sensitive, status="pending", attempted_at=now,
        )
        self.db.add(reply)
        await self.db.commit()  # the record exists before anything is sent
        return await self._deliver(reply, account, now, lambda client: client.reply_to_comment(comment.external_id, text), comment=comment)

    # ---------------- direct messages ----------------

    async def send_dm(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation: IgConversation,
        message: str,
        request_id: str,
        from_suggestion: bool = False,
        acknowledge_sensitive: bool = False,
        now: datetime | None = None,
    ) -> SocialReply:
        now = now or datetime.now(timezone.utc)
        if (earlier := await self._existing(organization_id, request_id)) is not None:
            return earlier
        text = clean_message(message)
        if not text:
            raise ValidationError("Write a reply first.")
        if len(text.encode()) > DM_LIMIT_BYTES:
            raise ValidationError(f"A message can be at most {DM_LIMIT_BYTES} bytes of text (this one is {len(text.encode())}). Shorten it.")
        if not conversation.participant_id:
            raise ValidationError("Who this conversation is with isn't known yet, so it can't be replied to from here. Sync again, or reply in the Instagram app.")
        expires = InboxService.window_expires(conversation)
        if expires is None or now > expires:
            raise ValidationError("The 24-hour window for replying has closed (Instagram only allows a reply within 24 hours of their last message, and can't start a conversation). Reply from the Instagram app instead.")
        if conversation.needs_care and not acknowledge_sensitive:
            raise ValidationError(f"{conversation.care_reason or 'This conversation needs careful handling.'} Confirm that you are handling it personally.")
        account = await self._account(organization_id, "messages", now)
        if await self._duplicate(organization_id, "dm", conversation.external_id, text, now):
            raise ValidationError("This exact message was already sent in this conversation a moment ago.")
        reply = SocialReply(
            organization_id=organization_id, user_id=user_id, request_id=request_id, kind="dm", conversation_id=conversation.id,
            target_external_id=conversation.external_id, message=text, source=self._source(text, conversation.suggested_reply, from_suggestion),
            acknowledged_sensitive=acknowledge_sensitive, status="pending", attempted_at=now,
        )
        self.db.add(reply)
        await self.db.commit()
        return await self._deliver(reply, account, now, lambda client: client.send_message(conversation.participant_id, text), conversation=conversation)

    # ---------------- the send, and what its answer means ----------------

    async def _deliver(self, reply: SocialReply, account: SocialAccount, now: datetime, send, comment: IgComment | None = None, conversation: IgConversation | None = None) -> SocialReply:
        try:
            client = await self._client(account)
            external_id = await send(client)
        except TokenUnreadable as exc:
            await self.connections._mark_failed(account, str(exc), now)
            return await self._finish(reply, "failed", error=f"{exc} Nothing was sent.", now=now)
        except InstagramError as exc:
            if exc.kind == "token":
                await self.connections._mark_failed(account, exc.message, now)
                return await self._finish(reply, "failed", error=f"{exc.message} Nothing was sent.", now=now)
            if exc.kind == "ambiguous":
                return await self._finish(
                    reply, "unknown", error=f"{exc.message} It will NOT be sent again automatically. Check Instagram, or use \"Check with Instagram\".", now=now
                )
            return await self._finish(reply, "failed", error=f"Not sent: {exc.message}", now=now)
        except Exception:  # noqa: BLE001 - after an unexpected error nobody knows whether the send went out
            logger.warning("social_reply_unexpected", reply_id=str(reply.id), exc_info=True)
            return await self._finish(reply, "unknown", error="Something unexpected happened while sending, so it isn't known whether the reply went out. Check Instagram before sending again.", now=now)
        await self._finish(reply, "sent", external_id=external_id, now=now, comment=comment, conversation=conversation)
        return reply

    async def _finish(
        self, reply: SocialReply, status: str, now: datetime, error: str | None = None, external_id: str | None = None,
        comment: IgComment | None = None, conversation: IgConversation | None = None,
    ) -> SocialReply:
        reply.status, reply.error, reply.finished_at = status, error, now
        if external_id:
            reply.external_reply_id = external_id
        if status == "sent":
            self._mark_target_answered(reply, now, comment, conversation)
        await self.db.commit()
        return reply

    def _mark_target_answered(self, reply: SocialReply, now: datetime, comment: IgComment | None, conversation: IgConversation | None) -> None:
        if comment is not None:
            comment.status, comment.handled_by_user_id = "answered", reply.user_id
        if conversation is not None:
            conversation.status, conversation.handled_by_user_id = "answered", reply.user_id
            conversation.last_message_from_us, conversation.last_message_at = True, now
            # shown in the thread at once; the next sync swaps in Instagram's own id for it (see inbox._store_message)
            self.db.add(IgMessage(organization_id=reply.organization_id, conversation_id=conversation.id, external_id=f"reply:{reply.id}", direction="out", text=reply.message, sent_at=now))

    # ---------------- an unclear outcome ----------------

    async def reconcile(self, reply: SocialReply, now: datetime | None = None) -> tuple[SocialReply, str]:
        """Ask Instagram whether an unclear reply went out. It never sends anything. Returns the reply and a short note."""
        now = now or datetime.now(timezone.utc)
        if reply.status != "unknown":
            raise ConflictError("Only a reply whose outcome is unclear needs checking.")
        account = await self.connections.get(reply.organization_id)
        if account is None or not account.token_encrypted:
            raise ValidationError("Instagram isn't connected, so it can't be checked from here.")
        since = (reply.attempted_at or reply.created_at) - CHECK_SLACK
        try:
            client = await self._client(account)
            found = await (self._find_comment_reply if reply.kind == "comment" else self._find_dm)(client, account, reply, since)
        except (InstagramError, TokenUnreadable) as exc:
            return reply, f"Instagram couldn't settle it: {getattr(exc, 'message', str(exc))}"
        comment = await self.db.get(IgComment, reply.comment_id) if reply.comment_id else None
        conversation = await self.db.get(IgConversation, reply.conversation_id) if reply.conversation_id else None
        if found:
            await self._finish(reply, "sent", now=now, external_id=found, comment=comment, conversation=conversation)
            return reply, "Found on Instagram: the reply was sent."
        await self._finish(reply, "failed", now=now, error="Instagram shows no such reply, so it was not sent. You can send it again.")
        return reply, "Not found on Instagram: it was not sent."

    async def _find_comment_reply(self, client: instagram.InstagramClient, account: SocialAccount, reply: SocialReply, since: datetime) -> str | None:
        for item in await client.list_replies(reply.target_external_id):
            if not isinstance(item, dict) or (item.get("text") or "").strip() != reply.message.strip():
                continue
            author = item.get("from") if isinstance(item.get("from"), dict) else {}
            mine = str(author.get("id") or "") == account.external_account_id or (item.get("username") or author.get("username") or "").lower() == (account.username or "-").lower()
            stamp = parse_time(item.get("timestamp"))
            if mine and stamp and stamp >= since:
                return str(item.get("id"))
        return None

    async def _find_dm(self, client: instagram.InstagramClient, account: SocialAccount, reply: SocialReply, since: datetime) -> str | None:
        for entry in (await client.conversation_message_ids(reply.target_external_id))[:5]:
            detail = await client.get_message(str(entry["id"]))
            author = detail.get("from") if isinstance(detail.get("from"), dict) else {}
            stamp = parse_time(detail.get("created_time"))
            if str(author.get("id") or "") == account.external_account_id and (detail.get("message") or "").strip() == reply.message.strip() and stamp and stamp >= since:
                return str(detail.get("id") or entry["id"])
        return None

    async def resolve(self, reply: SocialReply, sent: bool, now: datetime | None = None) -> SocialReply:
        """A person looked at Instagram and says whether it went out."""
        if reply.status != "unknown":
            raise ConflictError("Only a reply whose outcome is unclear needs resolving.")
        now = now or datetime.now(timezone.utc)
        if sent:
            comment = await self.db.get(IgComment, reply.comment_id) if reply.comment_id else None
            conversation = await self.db.get(IgConversation, reply.conversation_id) if reply.conversation_id else None
            await self._finish(reply, "sent", now=now, comment=comment, conversation=conversation)
            reply.error = "Recorded as sent by a person who checked Instagram."
        else:
            await self._finish(reply, "failed", now=now, error="Recorded as not sent by a person who checked Instagram.")
        await self.db.commit()
        return reply

    async def get(self, organization_id: uuid.UUID, reply_id: uuid.UUID) -> SocialReply:
        row = (await self.db.execute(select(SocialReply).where(SocialReply.id == reply_id, SocialReply.organization_id == organization_id))).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Reply not found.")
        return row

    async def history(self, organization_id: uuid.UUID, limit: int = 50) -> list[SocialReply]:
        return list((await self.db.execute(select(SocialReply).where(SocialReply.organization_id == organization_id).order_by(SocialReply.created_at.desc()).limit(limit))).scalars())
