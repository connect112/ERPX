"""The inbox: comments and direct messages to read, AI suggestions to look at, and replies a person sends by hand.

Reading and suggesting need `social_media.inbox`. Sending needs `social_media.inbox` AND `social_media.reply`, and every
send is an explicit request from a person: there is no route, task or webhook that sends a reply on its own."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.social_media.connection import ConnectionService, computed_status
from modules.social_media.inbox import InboxService, parse_time
from modules.social_media.models import IgComment, IgConversation, IgMedia, SocialPost, SocialReply
from modules.social_media.publish_routes import _thumbnail
from modules.social_media.replies import ReplyService
from modules.social_media.schemas import (
    AiSuggestion,
    CommentList,
    CommentOut,
    ConversationList,
    ConversationOut,
    HandledRequest,
    InboxSummary,
    MediaRef,
    MessageOut,
    ReconcileReplyOut,
    ReplyLine,
    ReplyOut,
    ReplyRequest,
    ResolveReplyRequest,
    SyncOut,
    ThreadOut,
    Triage,
)
from modules.social_media.service import SettingsService
from modules.social_media.suggest import Suggester
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

INBOX = "social_media.inbox"
REPLY = "social_media.reply"
READ_NOTE = (
    "Instagram doesn't tell us which messages you have read, so 'needs a reply' means their message is the latest in the conversation. "
    "Comments are read for the latest posts only. Labels such as 'enquiry' come from simple keyword rules, not from understanding."
)


async def _names(db: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    rows = await db.execute(select(User.id, User.full_name).where(User.id.in_(wanted)))
    return {i: n for i, n in rows.all()}


def _reply_out(reply: SocialReply, names: dict) -> ReplyOut:
    out = ReplyOut.model_validate(reply)
    out.sent_by = names.get(reply.user_id)
    return out


def _triage(row: IgComment | IgConversation) -> Triage:
    return Triage(category=row.category, priority=row.priority, needs_care=row.needs_care, care_reason=row.care_reason)


def _suggestion(row: IgComment | IgConversation) -> AiSuggestion:
    return AiSuggestion(summary=row.summary, reply=row.suggested_reply, note=row.suggestion_note, at=row.suggestion_at)


def _conversation_out(c: IgConversation, preview: str | None, now: datetime) -> ConversationOut:
    expires = InboxService.window_expires(c)
    return ConversationOut(
        id=c.id, participant_username=c.participant_username, participant_known=bool(c.participant_id), last_message_at=c.last_message_at,
        last_user_message_at=c.last_user_message_at, window_expires_at=expires, window_open=bool(expires and now <= expires), status=c.status,
        triage=_triage(c), suggestion=_suggestion(c), preview=preview,
    )


async def _comments_out(db: AsyncSession, organization_id: uuid.UUID, rows: list[IgComment]) -> list[CommentOut]:
    media_ids = {r.media_external_id for r in rows if r.media_external_id}
    media = {m.external_id: m for m in (await db.execute(select(IgMedia).where(IgMedia.organization_id == organization_id, IgMedia.external_id.in_(media_ids)))).scalars()} if media_ids else {}
    posts = {}
    post_ids = {m.post_id for m in media.values() if m.post_id}
    if post_ids:
        posts = {p.id: p for p in (await db.execute(select(SocialPost).where(SocialPost.id.in_(post_ids)))).scalars()}
    ours = {}
    own_ids = [r.id for r in rows]
    erpx = (await db.execute(select(SocialReply).where(SocialReply.organization_id == organization_id, SocialReply.comment_id.in_(own_ids)).order_by(SocialReply.created_at))).scalars().all() if own_ids else []
    for reply in erpx:
        ours.setdefault(reply.comment_id, []).append(reply)
    parents = [r.external_id for r in rows]
    own_comments = (
        (await db.execute(select(IgComment).where(IgComment.organization_id == organization_id, IgComment.parent_external_id.in_(parents), IgComment.is_own.is_(True)))).scalars().all()
        if parents
        else []
    )
    names = await _names(db, {r.user_id for r in erpx})
    out = []
    for row in rows:
        lines = [ReplyLine(id=str(r.id), text=r.message, at=r.finished_at or r.attempted_at, by="erpx", status=r.status, sent_by=names.get(r.user_id)) for r in ours.get(row.id, [])]
        sent_ids = {r.external_reply_id for r in ours.get(row.id, []) if r.external_reply_id}
        for own in own_comments:
            if own.parent_external_id == row.external_id and own.external_id not in sent_ids:
                lines.append(ReplyLine(id=own.external_id, text=own.text, at=own.posted_at, by="instagram", status="sent"))
        m = media.get(row.media_external_id or "")
        post = posts.get(m.post_id) if m and m.post_id else None
        out.append(
            CommentOut(
                id=row.id, text=row.text, author_username=row.author_username, author_known=bool(row.author_username), posted_at=row.posted_at,
                status=row.status, triage=_triage(row), suggestion=_suggestion(row),
                media=MediaRef(external_id=m.external_id, caption=(m.caption or "")[:140] or None, permalink=m.permalink, thumbnail_url=m.thumbnail_url, artwork_url=_thumbnail(post) if post else None, post_id=m.post_id) if m else None,
                replies=sorted(lines, key=lambda l: l.at or datetime.min.replace(tzinfo=timezone.utc)),
            )
        )
    return out


# ---------------- summary and sync ----------------


@router.get("/inbox/summary", response_model=InboxSummary)
async def inbox_summary(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    account = await ConnectionService(db).get(organization_id)
    now = datetime.now(timezone.utc)
    connected = computed_status(account, now) in ("connected", "expiring")
    caps = (account.capabilities or {}) if account else {}
    state = (account.sync_state or {}) if account else {}
    result = InboxSummary(
        connected=connected,
        can_read_comments=connected and caps.get("comments") not in ("unavailable",),
        can_read_messages=connected and caps.get("messages") not in ("unavailable", "needs_app_review"),
        counts=await InboxService(db).counts(organization_id),
        last_sync_at=parse_time((state.get("inbox") or {}).get("last_at")),
        stages=(state.get("inbox") or {}).get("stages", {}),
        note=READ_NOTE,
    )
    await db.commit()
    return result


@router.post("/inbox/sync", response_model=SyncOut)
async def sync_inbox(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    """Read the latest comments and messages from Instagram now (at most once a minute)."""
    result = await InboxService(db).sync(organization_id)
    await db.commit()
    return SyncOut(**result)


# ---------------- comments ----------------


@router.get("/comments", response_model=CommentList)
async def list_comments(
    view: str = Query(default="unanswered", pattern=r"^(unanswered|recent|enquiries|complaints|spam|all)$"),
    q: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await InboxService(db).list_comments(organization_id, view, q, skip, limit)
    result = CommentList(items=await _comments_out(db, organization_id, rows), total=total)
    await db.commit()
    return result


@router.post("/comments/{comment_id}/suggest", response_model=CommentOut)
async def suggest_comment(
    comment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    """An AI-drafted summary and possible reply. It is only a draft: nothing is sent."""
    inbox = InboxService(db)
    comment = await inbox.get_comment(organization_id, comment_id)
    await Suggester(db).for_comment(organization_id, user.id, await SettingsService(db).get(organization_id), comment)
    result = (await _comments_out(db, organization_id, [comment]))[0]
    await db.commit()
    return result


@router.post("/comments/{comment_id}/reply", response_model=ReplyOut)
async def reply_to_comment(
    comment_id: uuid.UUID,
    payload: ReplyRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX, REPLY)),
    db: AsyncSession = Depends(get_db),
):
    """Post a public reply, because a person asked to. The result says exactly what happened: sent, failed (not sent) or
    unknown (may have gone out; check before sending again)."""
    comment = await InboxService(db).get_comment(organization_id, comment_id)
    reply = await ReplyService(db).send_comment(
        organization_id, user.id, comment, payload.message, payload.request_id, payload.from_suggestion, payload.acknowledge_sensitive
    )
    result = _reply_out(reply, await _names(db, {reply.user_id}))
    await db.commit()
    return result


@router.post("/comments/{comment_id}/handled", response_model=CommentOut)
async def mark_comment(
    comment_id: uuid.UUID,
    payload: HandledRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    """Put a comment aside without replying (or bring it back). Nothing is posted or deleted."""
    comment = await InboxService(db).get_comment(organization_id, comment_id)
    comment.status = "ignored" if payload.action == "ignore" else "new"
    comment.handled_by_user_id = user.id if payload.action == "ignore" else None
    await db.flush()
    result = (await _comments_out(db, organization_id, [comment]))[0]
    await db.commit()
    return result


# ---------------- conversations ----------------


@router.get("/conversations", response_model=ConversationList)
async def list_conversations(
    view: str = Query(default="needs_reply", pattern=r"^(needs_reply|enquiries|complaints|high_priority|all)$"),
    q: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    inbox = InboxService(db)
    rows, total = await inbox.list_conversations(organization_id, view, q, skip, limit)
    now = datetime.now(timezone.utc)
    items = []
    for row in rows:
        latest = (await inbox.messages(row.id, 1))
        preview = (latest[-1].text or "[attachment]")[:120] if latest else None
        items.append(_conversation_out(row, preview, now))
    await db.commit()
    return ConversationList(items=items, total=total)


@router.get("/conversations/{conversation_id}", response_model=ThreadOut)
async def get_thread(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    inbox = InboxService(db)
    conversation = await inbox.get_conversation(organization_id, conversation_id)
    messages = await inbox.messages(conversation.id)
    history = await inbox.reply_history(organization_id, conversation_id=conversation.id)
    names = await _names(db, {r.user_id for r in history})
    result = ThreadOut(
        conversation=_conversation_out(conversation, None, datetime.now(timezone.utc)),
        messages=[MessageOut(id=m.id, direction=m.direction, text=m.text, sent_at=m.sent_at) for m in messages],
        replies=[ReplyLine(id=str(r.id), text=r.message, at=r.finished_at or r.attempted_at, by="erpx", status=r.status, sent_by=names.get(r.user_id)) for r in reversed(history)],
    )
    await db.commit()
    return result


@router.post("/conversations/{conversation_id}/suggest", response_model=ConversationOut)
async def suggest_conversation(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    """An AI-drafted summary and possible reply. It is only a draft: nothing is sent."""
    conversation = await InboxService(db).get_conversation(organization_id, conversation_id)
    await Suggester(db).for_conversation(organization_id, user.id, await SettingsService(db).get(organization_id), conversation)
    result = _conversation_out(conversation, None, datetime.now(timezone.utc))
    await db.commit()
    return result


@router.post("/conversations/{conversation_id}/reply", response_model=ReplyOut)
async def reply_to_conversation(
    conversation_id: uuid.UUID,
    payload: ReplyRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX, REPLY)),
    db: AsyncSession = Depends(get_db),
):
    """Send a direct message, because a person asked to (only within 24 hours of their last message)."""
    conversation = await InboxService(db).get_conversation(organization_id, conversation_id)
    reply = await ReplyService(db).send_dm(
        organization_id, user.id, conversation, payload.message, payload.request_id, payload.from_suggestion, payload.acknowledge_sensitive
    )
    result = _reply_out(reply, await _names(db, {reply.user_id}))
    await db.commit()
    return result


@router.post("/conversations/{conversation_id}/handled", response_model=ConversationOut)
async def mark_conversation(
    conversation_id: uuid.UUID,
    payload: HandledRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    """Put a conversation aside without replying (or bring it back). Nothing is sent."""
    conversation = await InboxService(db).get_conversation(organization_id, conversation_id)
    if payload.action == "ignore":
        conversation.status, conversation.handled_by_user_id = "ignored", user.id
    else:
        conversation.status = "answered" if conversation.last_message_from_us else "open"
    await db.flush()
    result = _conversation_out(conversation, None, datetime.now(timezone.utc))
    await db.commit()
    return result


# ---------------- the record of what was sent ----------------


@router.get("/replies", response_model=list[ReplyOut])
async def reply_history(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX)),
    db: AsyncSession = Depends(get_db),
):
    """Every reply anyone sent from here, with who sent it, the exact text, where it came from and how it ended."""
    rows = await ReplyService(db).history(organization_id)
    names = await _names(db, {r.user_id for r in rows})
    return [_reply_out(r, names) for r in rows]


@router.post("/replies/{reply_id}/reconcile", response_model=ReconcileReplyOut)
async def reconcile_reply(
    reply_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX, REPLY)),
    db: AsyncSession = Depends(get_db),
):
    """Ask Instagram whether an unclear reply went out. It never sends anything."""
    service = ReplyService(db)
    reply, note = await service.reconcile(await service.get(organization_id, reply_id))
    result = ReconcileReplyOut(note=note, reply=_reply_out(reply, await _names(db, {reply.user_id})))
    await db.commit()
    return result


@router.post("/replies/{reply_id}/resolve", response_model=ReplyOut)
async def resolve_reply(
    reply_id: uuid.UUID,
    payload: ResolveReplyRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(INBOX, REPLY)),
    db: AsyncSession = Depends(get_db),
):
    """A person looked at Instagram and records whether the reply is there."""
    service = ReplyService(db)
    reply = await service.resolve(await service.get(organization_id, reply_id), payload.sent)
    result = _reply_out(reply, await _names(db, {reply.user_id}))
    await db.commit()
    return result
