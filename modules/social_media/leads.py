"""
Turning an enquiry into a CRM lead, by a person, on purpose.

Not every comment is a lead. Nothing here runs by itself: a team member looks at a comment or a message, decides it is a genuine
enquiry, and creates the lead (with the CRM's own `crm.leads.manage` permission). ERPX only suggests which course the words
mention; the person confirms it. A lead made this way is the only attribution evidence ERPX keeps, and the record says so.

Only what is needed is kept: a name, optionally a phone number or email typed by the person (never taken from Instagram), the
Instagram handle (already public), the course of interest and a note. A direct message's text is not copied into the CRM.
Follow-ups made here are internal reminders (call, email, meeting, other): the CRM's WhatsApp and SMS follow-ups send a message to
the lead on their own, so they are not offered from here.
"""

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from modules.authentication.models import User
from modules.courses.models import Course
from modules.crm.followups.models import FollowUpType
from modules.crm.followups.repository import FollowUpRepository
from modules.crm.leads.models import Lead, LeadSource
from modules.crm.leads.service import LeadService
from modules.marketing.campaigns.models import Campaign
from modules.social_media.models import IgComment, IgConversation, IgMedia, LeadLink, TrackedLink

QUIET_FOLLOW_UPS = (FollowUpType.CALL, FollowUpType.EMAIL, FollowUpType.MEETING, FollowUpType.OTHER)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9][0-9 \-()]{5,28}$")
_WORDS = re.compile(r"[a-z0-9+#]{3,}")
_STOP = {"the", "and", "for", "with", "course", "courses", "training", "program", "programme", "batch", "class", "classes", "online", "offline", "fee", "fees", "how", "much", "what", "when", "your", "you", "this", "that", "about", "please", "details", "information", "info"}


def _tokens(text: str) -> set[str]:
    return {w for w in _WORDS.findall(text.lower()) if w not in _STOP}


async def suggest_course(db: AsyncSession, organization_id: uuid.UUID, text: str) -> dict | None:
    """Which published course the words mention, if any. A suggestion for a person to confirm, never an assignment."""
    wanted = _tokens(text)
    if not wanted:
        return None
    best: tuple[int, Course, set[str]] | None = None
    courses = (await db.execute(select(Course).where(Course.organization_id == organization_id, Course.is_published.is_(True), Course.deleted_at.is_(None)))).scalars()
    for course in courses:
        hits = wanted & _tokens(course.title)
        if hits and (best is None or len(hits) > best[0]):
            best = (len(hits), course, hits)
    if best is None:
        return None
    return {"course_id": best[1].id, "title": best[1].title, "matched": sorted(best[2])}


class SocialLeadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _check(self, organization_id: uuid.UUID, data: dict) -> tuple[Course | None, TrackedLink | None, Campaign | None]:
        name = (data.get("full_name") or "").strip()
        if not name:
            raise ValidationError("A name is needed to create a lead.")
        if data.get("email") and not _EMAIL.match(data["email"].strip()):
            raise ValidationError("That email address doesn't look right.")
        if data.get("phone") and not _PHONE.match(data["phone"].strip()):
            raise ValidationError("That phone number doesn't look right.")
        course = None
        if data.get("course_id"):
            course = (await self.db.execute(select(Course).where(Course.id == data["course_id"], Course.organization_id == organization_id, Course.deleted_at.is_(None)))).scalar_one_or_none()
            if course is None:
                raise ValidationError("That course doesn't exist.")
        link = None
        if data.get("link_id"):
            link = (await self.db.execute(select(TrackedLink).where(TrackedLink.id == data["link_id"], TrackedLink.organization_id == organization_id))).scalar_one_or_none()
            if link is None:
                raise ValidationError("That tracked link doesn't exist.")
        campaign_id = data.get("marketing_campaign_id") or (link.marketing_campaign_id if link else None)
        campaign = None
        if campaign_id:
            campaign = (await self.db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.organization_id == organization_id))).scalar_one_or_none()
            if campaign is None:
                raise ValidationError("That campaign doesn't exist.")
        if data.get("assigned_to_user_id"):
            known = (await self.db.execute(select(User.id).where(User.id == data["assigned_to_user_id"]))).scalar_one_or_none()
            if known is None:
                raise ValidationError("That team member doesn't exist.")
        follow = data.get("follow_up")
        if follow:
            if follow["type"] not in {t.value for t in QUIET_FOLLOW_UPS}:
                raise ValidationError("A follow-up made here is a reminder for the team (call, email, meeting or other). WhatsApp and SMS follow-ups send a message by themselves, so make those in the CRM.")
            if follow["scheduled_at"].tzinfo is None:
                follow["scheduled_at"] = follow["scheduled_at"].replace(tzinfo=timezone.utc)
            if follow["scheduled_at"] <= datetime.now(timezone.utc):
                raise ValidationError("Choose a follow-up time in the future.")
        return course, link, campaign

    async def _warnings(self, organization_id: uuid.UUID, handle: str | None) -> list[str]:
        if not handle:
            return []
        rows = (await self.db.execute(select(LeadLink.created_at).where(LeadLink.organization_id == organization_id, func.lower(LeadLink.handle) == handle.lower()).order_by(LeadLink.created_at.desc()).limit(1))).scalar_one_or_none()
        return [f"A lead was already created for @{handle} on {rows:%d %b %Y}. Check the CRM so the same person isn't added twice."] if rows else []

    async def from_comment(self, organization_id: uuid.UUID, user: User, comment: IgComment, data: dict) -> dict:
        if comment.is_own:
            raise NotFoundError("Comment not found.")
        if (await self.db.execute(select(LeadLink.id).where(LeadLink.comment_id == comment.id))).scalar_one_or_none():
            raise ValidationError("A lead was already created from this comment.")
        media = None
        if comment.media_external_id:
            media = (await self.db.execute(select(IgMedia).where(IgMedia.organization_id == organization_id, IgMedia.external_id == comment.media_external_id))).scalar_one_or_none()
        where = f"the post \"{(media.caption or 'a post')[:60]}\"" if media else "a post"
        return await self._create(
            organization_id, user, data, origin="comment", handle=comment.author_username, comment_id=comment.id, conversation_id=None,
            media_external_id=comment.media_external_id, post_id=media.post_id if media else None,
            where=f"a comment on {where}", basis=f"{user.full_name} created this lead from a comment by @{comment.author_username or 'unknown'} on {where}.",
        )

    async def from_conversation(self, organization_id: uuid.UUID, user: User, conversation: IgConversation, data: dict) -> dict:
        if (await self.db.execute(select(LeadLink.id).where(LeadLink.conversation_id == conversation.id))).scalar_one_or_none():
            raise ValidationError("A lead was already created from this conversation.")
        return await self._create(
            organization_id, user, data, origin="message", handle=conversation.participant_username, comment_id=None, conversation_id=conversation.id,
            media_external_id=None, post_id=None, where="a direct message", basis=f"{user.full_name} created this lead from a direct message from @{conversation.participant_username or 'unknown'}.",
        )

    async def _create(self, organization_id: uuid.UUID, user: User, data: dict, *, origin: str, handle: str | None, comment_id, conversation_id, media_external_id, post_id, where: str, basis: str) -> dict:
        course, link, campaign = await self._check(organization_id, data)
        warnings = await self._warnings(organization_id, handle)
        label = course.title if course else ((data.get("course_label") or "").strip() or None)
        note = (data.get("note") or "").strip()
        notes = f"Instagram lead. Handle: @{handle or 'unknown'}. Came from {where}." + (f" Interested in: {label}." if label else "") + (f" {note}" if note else "")
        lead = await LeadService(self.db).create_lead(
            organization_id, full_name=data["full_name"].strip(), email=(data.get("email") or "").strip() or None, phone=(data.get("phone") or "").strip() or None,
            source=LeadSource.SOCIAL_MEDIA, campaign_id=campaign.id if campaign else None, assigned_to_user_id=data.get("assigned_to_user_id"), notes=notes[:4000],
        )
        if link is not None:
            basis += f" The team member linked it to the tracked link \"{link.name}\"; that is their judgement, not something ERPX can see."
        basis += " Nothing shows that Instagram caused the enquiry."
        row = LeadLink(
            organization_id=organization_id, lead_id=lead.id, created_by_user_id=user.id, origin=origin if link is None else "link", comment_id=comment_id, conversation_id=conversation_id,
            link_id=link.id if link else None, post_id=post_id or (link.post_id if link else None), media_external_id=media_external_id, course_label=label, handle=handle, basis=basis[:400],
        )
        self.db.add(row)
        follow_id = None
        follow = data.get("follow_up")
        if follow:
            created = await FollowUpRepository(self.db).create(lead_id=lead.id, created_by_user_id=user.id, follow_up_type=FollowUpType(follow["type"]), scheduled_at=follow["scheduled_at"], notes=(follow.get("notes") or None))
            follow_id = created.id
        await self.db.flush()
        return {"lead_id": lead.id, "link_id": row.id, "follow_up_id": follow_id, "warnings": warnings, "basis": row.basis}
