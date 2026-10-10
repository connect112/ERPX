"""
Retention and erasure of personal data.

What the retention period (Settings) removes, once it has passed:
- comments, conversations and messages (the words and the people's handles)
- the text of replies a team member sent (the record of who sent one, when, and how it ended is kept: that is the audit trail)
- Instagram's notification records after 30 days (ids only)
- posts read from Instagram and their per-post figures, and the AI drafts stored with comments and messages

What it does not remove, and why: weekly and monthly reports and the daily account figures hold only counts, no personal
data; the CRM keeps its own leads under its own rules (a lead made from a comment keeps working even after the comment is gone);
the audit trail never held comment, message or reply text in the first place.

`erase_person` removes one person's comments, conversations, messages and the text of replies to them, on request.
Both can show what they would remove before doing it.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.social_media.models import (
    IgComment,
    IgConversation,
    IgMedia,
    IgMessage,
    LeadLink,
    MediaMetric,
    SocialReply,
    SocialSettings,
    WebhookEvent,
)

REMOVED_TEXT = "[removed under the retention policy]"
ERASED_TEXT = "[erased at the person's request]"
WEBHOOK_DAYS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _count(db: AsyncSession, query) -> int:
    return (await db.execute(query)).scalar_one()


async def preview(db: AsyncSession, organization_id: uuid.UUID, retention_days: int, now: datetime | None = None) -> dict:
    now = now or utcnow()
    cutoff = now - timedelta(days=retention_days)
    return {
        "cutoff": cutoff,
        "messages": await _count(db, select(func.count()).select_from(IgMessage).where(IgMessage.organization_id == organization_id, IgMessage.sent_at < cutoff)),
        "conversations": await _count(db, select(func.count()).select_from(IgConversation).where(IgConversation.organization_id == organization_id, IgConversation.last_message_at < cutoff)),
        "comments": await _count(db, select(func.count()).select_from(IgComment).where(IgComment.organization_id == organization_id, IgComment.posted_at < cutoff)),
        "reply_texts": await _count(db, select(func.count()).select_from(SocialReply).where(SocialReply.organization_id == organization_id, SocialReply.created_at < cutoff, SocialReply.message.notin_((REMOVED_TEXT, ERASED_TEXT)))),
        "posts_read": await _count(db, select(func.count()).select_from(IgMedia).where(IgMedia.organization_id == organization_id, IgMedia.posted_at < cutoff)),
        "notifications": await _count(db, select(func.count()).select_from(WebhookEvent).where(WebhookEvent.organization_id == organization_id, WebhookEvent.created_at < now - timedelta(days=WEBHOOK_DAYS))),
    }


async def apply(db: AsyncSession, organization_id: uuid.UUID, retention_days: int, now: datetime | None = None) -> dict:
    """Remove what is past the retention period. Safe to run again: a second run finds nothing more."""
    now = now or utcnow()
    cutoff = now - timedelta(days=retention_days)
    org = organization_id
    removed = {}
    removed["messages"] = (await db.execute(delete(IgMessage).where(IgMessage.organization_id == org, IgMessage.sent_at < cutoff))).rowcount or 0
    removed["conversations"] = (await db.execute(delete(IgConversation).where(IgConversation.organization_id == org, IgConversation.last_message_at < cutoff))).rowcount or 0
    removed["comments"] = (await db.execute(delete(IgComment).where(IgComment.organization_id == org, IgComment.posted_at < cutoff))).rowcount or 0
    removed["reply_texts"] = (
        await db.execute(
            update(SocialReply)
            .where(SocialReply.organization_id == org, SocialReply.created_at < cutoff, SocialReply.message.notin_((REMOVED_TEXT, ERASED_TEXT)))
            .values(message=REMOVED_TEXT)
        )
    ).rowcount or 0
    old = [m for m in (await db.execute(select(IgMedia.external_id).where(IgMedia.organization_id == org, IgMedia.posted_at < cutoff))).scalars()]
    if old:
        await db.execute(delete(MediaMetric).where(MediaMetric.organization_id == org, MediaMetric.media_external_id.in_(old)))
        await db.execute(delete(IgMedia).where(IgMedia.organization_id == org, IgMedia.external_id.in_(old)))
    removed["posts_read"] = len(old)
    removed["notifications"] = (await db.execute(delete(WebhookEvent).where(WebhookEvent.organization_id == org, WebhookEvent.created_at < now - timedelta(days=WEBHOOK_DAYS)))).rowcount or 0
    await db.flush()
    return removed


async def apply_all(db: AsyncSession, now: datetime | None = None) -> dict:
    total: dict[str, int] = {}
    for org_id, days in (await db.execute(select(SocialSettings.organization_id, SocialSettings.retention_days))).all():
        for key, value in (await apply(db, org_id, days, now)).items():
            total[key] = total.get(key, 0) + value
    return total


async def erase_person(db: AsyncSession, organization_id: uuid.UUID, handle: str, confirm: bool, now: datetime | None = None) -> dict:
    """Remove one person's comments, conversations and messages and the text of replies to them. Without `confirm` it only counts."""
    who = handle.strip().lstrip("@").lower()
    org = organization_id
    comments = list((await db.execute(select(IgComment.id).where(IgComment.organization_id == org, func.lower(IgComment.author_username) == who))).scalars())
    conversations = list((await db.execute(select(IgConversation.id).where(IgConversation.organization_id == org, func.lower(IgConversation.participant_username) == who))).scalars())
    messages = await _count(db, select(func.count()).select_from(IgMessage).where(IgMessage.organization_id == org, IgMessage.conversation_id.in_(conversations))) if conversations else 0
    replies = list(
        (
            await db.execute(
                select(SocialReply.id).where(
                    SocialReply.organization_id == org, (SocialReply.comment_id.in_(comments)) | (SocialReply.conversation_id.in_(conversations)), SocialReply.message != ERASED_TEXT
                )
            )
        ).scalars()
    ) if (comments or conversations) else []
    leads = await _count(db, select(func.count()).select_from(LeadLink).where(LeadLink.organization_id == org, func.lower(LeadLink.handle) == who))
    result = {"comments": len(comments), "conversations": len(conversations), "messages": messages, "reply_texts": len(replies), "crm_leads": leads, "erased": False}
    if not confirm or not (comments or conversations or replies):
        return result
    if replies:
        await db.execute(update(SocialReply).where(SocialReply.id.in_(replies)).values(message=ERASED_TEXT))
    if comments:
        await db.execute(delete(IgComment).where(IgComment.id.in_(comments)))
    if conversations:
        await db.execute(delete(IgConversation).where(IgConversation.id.in_(conversations)))
    if leads:
        await db.execute(update(LeadLink).where(LeadLink.organization_id == org, func.lower(LeadLink.handle) == who).values(handle=None, basis="The handle was erased at the person's request."))
    await db.flush()
    result["erased"] = True
    return result
