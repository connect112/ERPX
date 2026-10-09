"""
The inbox: reading the profile's comments and direct messages into ERPX so a person can see them and answer them by hand.

Reading is careful and light:
- only what Instagram allows and the account was granted; a feature that wasn't granted is skipped and says why
- incremental: conversations are only re-read when Instagram says they changed, messages already stored are not fetched again,
  and only the latest posts' comments are read; a manual "Sync now" waits at least a minute between runs
- anything that fails is recorded (never as zero) and a temporary problem stops that part of the run instead of hammering
- every comment and message is untrusted text: stored as text, labelled by plain rules (classify.py), shown escaped

Nothing in this module sends anything. Sending lives only in replies.py, behind an explicit action.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.social_media import instagram
from modules.social_media.classify import classify
from modules.social_media.connection import ConnectionService, computed_status
from modules.social_media.instagram import InstagramError
from modules.social_media.models import (
    IgComment,
    IgConversation,
    IgMedia,
    IgMessage,
    SocialAccount,
    SocialPost,
    SocialReply,
    WebhookEvent,
)
from modules.social_media.token_crypto import TokenUnreadable, decrypt_token

logger = get_logger(__name__)

MIN_INTERVAL = timedelta(seconds=60)
MEDIA_LIMIT = 25
COMMENT_MEDIA = 10  # comments are read for the latest posts only
COMMENT_PAGES = 2
CONVERSATION_LIMIT = 30
MESSAGES_PER_CONVERSATION = 20  # Instagram only returns details for the 20 most recent
DETAILS_PER_SYNC = 80
WINDOW = timedelta(hours=24)  # how long after a person's last message the account may reply


def parse_time(value: object) -> datetime | None:
    """Instagram gives times as ISO text ("2026-10-10T10:00:00+0000") or as Unix seconds."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str) and value:
        text = value.strip().replace("Z", "+00:00")
        if text.endswith("+0000") or text.endswith("-0000"):
            text = text[:-5] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return datetime.fromtimestamp(float(value), tz=timezone.utc) if value.replace(".", "", 1).isdigit() else None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _person(entry: object) -> tuple[str | None, str | None]:
    """(id, username) from a `from` object, whatever Instagram chose to include."""
    if isinstance(entry, dict):
        ident, name = entry.get("id"), entry.get("username")
        return (str(ident) if ident else None, str(name)[:100] if name else None)
    return None, None


class InboxService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- reading from Instagram ----------------

    async def sync(self, organization_id: uuid.UUID, now: datetime | None = None, force: bool = False) -> dict:
        now = now or datetime.now(timezone.utc)
        connections = ConnectionService(self.db)
        account = await connections.get(organization_id)
        if account is None or computed_status(account, now) not in ("connected", "expiring"):
            raise ConflictError("Instagram isn't connected, so there is nothing to read.")
        state = dict(account.sync_state or {})
        last = parse_time((state.get("inbox") or {}).get("last_at"))
        if not force and last and now - last < MIN_INTERVAL:
            seconds = int((now - last).total_seconds())
            return {"skipped": True, "message": f"Already read {seconds} seconds ago. Instagram is only asked at most once a minute.", "stages": state.get("inbox", {}).get("stages", {})}
        try:
            client = instagram.get_instagram_client(account.external_account_id, decrypt_token(account.token_encrypted or ""))
        except TokenUnreadable as exc:
            await connections._mark_failed(account, str(exc), now)
            raise ConflictError(str(exc)) from None

        caps = account.capabilities or {}
        stages: dict[str, dict] = {}
        for name, runner, allowed in (
            ("media", self._media, True),
            ("comments", self._comments, caps.get("comments") not in ("unavailable",)),
            ("messages", self._conversations, caps.get("messages") not in ("unavailable", "needs_app_review")),
        ):
            if not allowed:
                stages[name] = {"ok": False, "skipped": True, "error": "Instagram hasn't given this app permission for this (see Settings, Check what it can do)."}
                continue
            try:
                stages[name] = {"ok": True, "error": None, "count": await runner(account, client, now)}
            except InstagramError as exc:
                stages[name] = {"ok": False, "error": exc.message}
                if exc.kind == "token":
                    await connections._mark_failed(account, exc.message, now)
                    break
        for name, info in stages.items():
            state[name] = {"last_at": now.isoformat(), **info}
        state["inbox"] = {"last_at": now.isoformat(), "stages": stages}
        account.sync_state = state
        if any(s.get("ok") for s in stages.values()):
            account.last_synced_at = now
        await self.db.execute(
            update(WebhookEvent).where(WebhookEvent.organization_id == organization_id, WebhookEvent.processed_at.is_(None)).values(processed_at=now)
        )
        await self.db.flush()
        return {"skipped": False, "message": None, "stages": stages}

    async def _media(self, account: SocialAccount, client: instagram.InstagramClient, now: datetime) -> int:
        rows, _ = await client.media_page(MEDIA_LIMIT)
        known = {
            m.external_id: m
            for m in (await self.db.execute(select(IgMedia).where(IgMedia.organization_id == account.organization_id))).scalars()
        }
        ours = {
            p.external_media_id: p.id
            for p in (
                await self.db.execute(
                    select(SocialPost).where(SocialPost.organization_id == account.organization_id, SocialPost.external_media_id.is_not(None))
                )
            ).scalars()
        }
        count = 0
        for item in rows:
            ident = str(item.get("id") or "")
            if not ident:
                continue
            media = known.get(ident)
            if media is None:
                media = IgMedia(organization_id=account.organization_id, external_id=ident)
                self.db.add(media)
            media.media_type = str(item.get("media_type") or "")[:30] or None
            media.product_type = str(item.get("media_product_type") or "")[:30] or None
            media.caption = item.get("caption") if isinstance(item.get("caption"), str) else None
            media.permalink = str(item.get("permalink") or "")[:500] or None
            media.thumbnail_url = str(item.get("thumbnail_url") or item.get("media_url") or "")[:1000] or None
            media.posted_at = parse_time(item.get("timestamp"))
            media.comments_count = item.get("comments_count") if isinstance(item.get("comments_count"), int) else None
            media.post_id = ours.get(ident, media.post_id)
            media.synced_at = now
            count += 1
        await self.db.flush()
        return count

    def _is_own(self, account: SocialAccount, author_id: str | None, username: str | None) -> bool:
        if author_id and author_id == account.external_account_id:
            return True
        return bool(username and account.username and username.lower() == account.username.lower())

    async def _upsert_comment(
        self, account: SocialAccount, item: dict, media_id: str, parent_id: str | None, existing: dict[str, IgComment], now: datetime
    ) -> IgComment | None:
        ident = str(item.get("id") or "")
        if not ident:
            return None
        author_id, username = _person(item.get("from"))
        username = username or (str(item["username"])[:100] if item.get("username") else None)
        text = item.get("text") if isinstance(item.get("text"), str) else ""
        comment = existing.get(ident)
        created = comment is None
        if comment is None:
            comment = IgComment(organization_id=account.organization_id, external_id=ident, status="new")
            self.db.add(comment)
            existing[ident] = comment
        changed = created or comment.text != text
        comment.media_external_id = media_id
        comment.parent_external_id = parent_id
        comment.text = text
        comment.author_username = username or comment.author_username
        comment.author_id = author_id or comment.author_id
        comment.posted_at = parse_time(item.get("timestamp")) or comment.posted_at
        comment.is_own = self._is_own(account, comment.author_id, comment.author_username)
        comment.hidden = item.get("hidden") if isinstance(item.get("hidden"), bool) else comment.hidden
        comment.synced_at = now
        if comment.is_own:
            comment.status = "answered"
            comment.category, comment.priority, comment.needs_care, comment.care_reason = "other", "low", False, None
        elif changed:
            triage = classify(text)
            comment.category, comment.priority, comment.needs_care, comment.care_reason = triage.category, triage.priority, triage.needs_care, triage.care_reason
        return comment

    async def _comments(self, account: SocialAccount, client: instagram.InstagramClient, now: datetime) -> int:
        organization_id = account.organization_id
        media_rows = (
            await self.db.execute(
                select(IgMedia)
                .where(IgMedia.organization_id == organization_id, or_(IgMedia.comments_count.is_(None), IgMedia.comments_count > 0))
                .order_by(IgMedia.posted_at.desc().nullslast())
                .limit(COMMENT_MEDIA)
            )
        ).scalars().all()
        existing = {c.external_id: c for c in (await self.db.execute(select(IgComment).where(IgComment.organization_id == organization_id))).scalars()}
        count = 0
        for media in media_rows:
            after = None
            for _page in range(COMMENT_PAGES):
                rows, after = await client.list_comments(media.external_id, after=after)
                for item in rows:
                    top = await self._upsert_comment(account, item, media.external_id, None, existing, now)
                    if top is None:
                        continue
                    count += 1
                    replies = item.get("replies", {}).get("data", []) if isinstance(item.get("replies"), dict) else []
                    own_reply = False
                    for reply in replies if isinstance(replies, list) else []:
                        if isinstance(reply, dict):
                            saved = await self._upsert_comment(account, reply, media.external_id, top.external_id, existing, now)
                            own_reply = own_reply or bool(saved and saved.is_own)
                    # An answer given in the Instagram app counts too. Never undo an answer or an "ignore" a person recorded.
                    if own_reply and not top.is_own and top.status == "new":
                        top.status = "answered"
                if not after:
                    break
        await self.db.flush()
        return count

    async def _conversations(self, account: SocialAccount, client: instagram.InstagramClient, now: datetime) -> int:
        organization_id = account.organization_id
        listed: list[dict] = []
        after = None
        while len(listed) < CONVERSATION_LIMIT:
            rows, after = await client.conversations_page(25, after)
            listed.extend(rows)
            if not after or not rows:
                break
        listed = listed[:CONVERSATION_LIMIT]
        known = {c.external_id: c for c in (await self.db.execute(select(IgConversation).where(IgConversation.organization_id == organization_id))).scalars()}
        budget = DETAILS_PER_SYNC
        touched = 0
        for item in listed:
            ident = str(item.get("id") or "")
            if not ident:
                continue
            remote = parse_time(item.get("updated_time"))
            conversation = known.get(ident)
            if conversation is not None and remote and conversation.remote_updated_at and conversation.remote_updated_at >= remote:
                continue  # unchanged since it was last read
            if conversation is None:
                conversation = IgConversation(organization_id=organization_id, external_id=ident, status="open")
                self.db.add(conversation)
                await self.db.flush()
                known[ident] = conversation
            stored = {
                m for (m,) in (await self.db.execute(select(IgMessage.external_id).where(IgMessage.conversation_id == conversation.id)))
            }
            ids = await client.conversation_message_ids(ident)
            for entry in ids[:MESSAGES_PER_CONVERSATION]:
                message_id = str(entry["id"])
                if message_id in stored:
                    continue
                if budget <= 0:
                    break
                budget -= 1
                try:
                    detail = await client.get_message(message_id)
                except InstagramError as exc:
                    if exc.kind == "permanent":
                        continue  # an older message Instagram no longer returns
                    raise
                await self._store_message(account, conversation, detail, message_id)
            await self.db.flush()
            await self._refresh_conversation(conversation, remote, now)
            touched += 1
        await self.db.flush()
        return touched

    async def _store_message(self, account: SocialAccount, conversation: IgConversation, detail: dict, message_id: str) -> None:
        sender_id, sender_name = _person(detail.get("from"))
        outgoing = sender_id == account.external_account_id or bool(sender_name and account.username and sender_name.lower() == account.username.lower())
        text = detail.get("message") if isinstance(detail.get("message"), str) and detail.get("message") else None
        if outgoing and text:
            # A reply sent from ERPX is shown at once under a placeholder id; swap in Instagram's own id instead of duplicating it.
            placeholder = (
                await self.db.execute(
                    select(IgMessage).where(IgMessage.conversation_id == conversation.id, IgMessage.external_id.like("reply:%"), IgMessage.text == text).limit(1)
                )
            ).scalar_one_or_none()
            if placeholder is not None:
                placeholder.external_id = message_id
                placeholder.sent_at = parse_time(detail.get("created_time")) or placeholder.sent_at
                return
        self.db.add(
            IgMessage(
                organization_id=account.organization_id,
                conversation_id=conversation.id,
                external_id=message_id,
                direction="out" if outgoing else "in",
                text=text,
                sent_at=parse_time(detail.get("created_time")),
            )
        )
        if not outgoing and sender_id:
            conversation.participant_id, conversation.participant_username = sender_id, sender_name or conversation.participant_username
        elif outgoing and not conversation.participant_id:
            recipients = detail.get("to", {}).get("data", []) if isinstance(detail.get("to"), dict) else []
            if recipients and isinstance(recipients[0], dict) and recipients[0].get("id"):
                conversation.participant_id = str(recipients[0]["id"])
                conversation.participant_username = str(recipients[0].get("username") or "")[:100] or None

    async def _refresh_conversation(self, conversation: IgConversation, remote: datetime | None, now: datetime) -> None:
        """Recompute what a conversation looks like from the messages stored for it."""
        rows = (
            await self.db.execute(select(IgMessage).where(IgMessage.conversation_id == conversation.id).order_by(IgMessage.sent_at.desc().nullslast()))
        ).scalars().all()
        conversation.remote_updated_at = remote or conversation.remote_updated_at
        conversation.synced_at = now
        if not rows:
            return
        latest = rows[0]
        inbound = [m for m in rows if m.direction == "in"]
        conversation.last_message_at = latest.sent_at
        conversation.last_message_from_us = latest.direction == "out"
        conversation.last_user_message_at = inbound[0].sent_at if inbound else conversation.last_user_message_at
        if conversation.status != "ignored":
            conversation.status = "answered" if latest.direction == "out" else "open"
        recent_text = "\n".join(m.text for m in inbound[:3] if m.text)
        triage = classify(recent_text)
        conversation.category, conversation.priority, conversation.needs_care, conversation.care_reason = triage.category, triage.priority, triage.needs_care, triage.care_reason

    # ---------------- what the inbox shows ----------------

    @staticmethod
    def window_expires(conversation: IgConversation) -> datetime | None:
        return conversation.last_user_message_at + WINDOW if conversation.last_user_message_at else None

    async def counts(self, organization_id: uuid.UUID) -> dict:
        top = and_(IgComment.organization_id == organization_id, IgComment.parent_external_id.is_(None), IgComment.is_own.is_(False))
        unanswered = and_(top, IgComment.status == "new")

        async def count(*conditions) -> int:
            return (await self.db.execute(select(func.count()).select_from(IgComment).where(*conditions))).scalar_one()

        async def convo(*conditions) -> int:
            return (await self.db.execute(select(func.count()).select_from(IgConversation).where(IgConversation.organization_id == organization_id, *conditions))).scalar_one()

        return {
            "comments_unanswered": await count(unanswered),
            "comments_enquiries": await count(unanswered, IgComment.category == "enquiry"),
            "comments_high_priority": await count(unanswered, IgComment.priority == "high"),
            "messages_need_reply": await convo(IgConversation.status == "open"),
            "messages_enquiries": await convo(IgConversation.status == "open", IgConversation.category == "enquiry"),
            "messages_high_priority": await convo(IgConversation.status == "open", IgConversation.priority == "high"),
        }

    async def list_comments(self, organization_id: uuid.UUID, view: str, q: str | None, skip: int, limit: int, now: datetime | None = None) -> tuple[list[IgComment], int]:
        now = now or datetime.now(timezone.utc)
        conditions = [IgComment.organization_id == organization_id, IgComment.parent_external_id.is_(None), IgComment.is_own.is_(False)]
        if view == "unanswered":
            conditions.append(IgComment.status == "new")
        elif view == "recent":
            conditions += [IgComment.posted_at >= now - timedelta(days=7), IgComment.status != "ignored"]
        elif view == "enquiries":
            conditions.append(IgComment.category == "enquiry")
        elif view == "complaints":
            conditions.append(IgComment.category == "complaint")
        elif view == "spam":
            conditions.append(IgComment.category == "spam")
        if q:
            conditions.append(IgComment.text.ilike(f"%{q.strip()[:100]}%"))
        total = (await self.db.execute(select(func.count()).select_from(IgComment).where(*conditions))).scalar_one()
        rows = (await self.db.execute(select(IgComment).where(*conditions).order_by(IgComment.posted_at.desc().nullslast()).offset(skip).limit(limit))).scalars().all()
        return list(rows), total

    async def list_conversations(self, organization_id: uuid.UUID, view: str, q: str | None, skip: int, limit: int) -> tuple[list[IgConversation], int]:
        conditions = [IgConversation.organization_id == organization_id]
        if view == "needs_reply":
            conditions.append(IgConversation.status == "open")
        elif view == "enquiries":
            conditions.append(IgConversation.category == "enquiry")
        elif view == "complaints":
            conditions.append(IgConversation.category == "complaint")
        elif view == "high_priority":
            conditions += [IgConversation.priority == "high", IgConversation.status != "ignored"]
        if q:
            conditions.append(IgConversation.participant_username.ilike(f"%{q.strip()[:100]}%"))
        total = (await self.db.execute(select(func.count()).select_from(IgConversation).where(*conditions))).scalar_one()
        rows = (
            await self.db.execute(select(IgConversation).where(*conditions).order_by(IgConversation.last_message_at.desc().nullslast()).offset(skip).limit(limit))
        ).scalars().all()
        return list(rows), total

    async def get_comment(self, organization_id: uuid.UUID, comment_id: uuid.UUID) -> IgComment:
        row = (await self.db.execute(select(IgComment).where(IgComment.id == comment_id, IgComment.organization_id == organization_id))).scalar_one_or_none()
        if row is None or row.is_own:
            raise NotFoundError("Comment not found.")
        return row

    async def get_conversation(self, organization_id: uuid.UUID, conversation_id: uuid.UUID) -> IgConversation:
        row = (await self.db.execute(select(IgConversation).where(IgConversation.id == conversation_id, IgConversation.organization_id == organization_id))).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Conversation not found.")
        return row

    async def messages(self, conversation_id: uuid.UUID, limit: int = 60) -> list[IgMessage]:
        rows = (await self.db.execute(select(IgMessage).where(IgMessage.conversation_id == conversation_id).order_by(IgMessage.sent_at.desc().nullslast()).limit(limit))).scalars().all()
        return list(reversed(rows))

    async def reply_history(self, organization_id: uuid.UUID, *, comment_id: uuid.UUID | None = None, conversation_id: uuid.UUID | None = None, limit: int = 10) -> list[SocialReply]:
        conditions = [SocialReply.organization_id == organization_id]
        if comment_id:
            conditions.append(SocialReply.comment_id == comment_id)
        if conversation_id:
            conditions.append(SocialReply.conversation_id == conversation_id)
        return list((await self.db.execute(select(SocialReply).where(*conditions).order_by(SocialReply.created_at.desc()).limit(limit))).scalars())
