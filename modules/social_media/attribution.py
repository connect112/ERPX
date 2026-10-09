"""
From enquiry to enrolment, reported without inventing credit.

What is counted:
- enquiries: comments and messages the plain-rule labeller thought were enquiries (a rough pointer, not a judgement)
- leads linked: CRM leads a team member created from a comment, a message or a tracked link
- how far those leads got, as the CRM shows today: contacted, qualified, applied (an admission exists), enrolled (converted)
- tracked-link opens, shown beside the leads and never turned into a conversion rate

What is NOT claimed: that a post, link or campaign caused anyone to enrol. A lead appears here only because a person linked it, so
people who enquired some other way, or who saw the posts and never commented, are invisible. The report says so every time.
"""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.authentication.models import User
from modules.crm.admissions.models import Admission, AdmissionStatus
from modules.crm.followups.models import FollowUp, FollowUpStatus
from modules.crm.leads.models import Lead, LeadStatus
from modules.social_media.links import LinkService, short_url
from modules.social_media.models import IgComment, IgConversation, IgMedia, LeadLink, SocialPost, TrackedLink

ASSUMPTIONS = [
    "A lead is counted here only because a team member created it from a comment, a message or a tracked link. People who enquired another way, or who saw the posts and never wrote, are not visible to ERPX.",
    "Linking a lead to a post or link is the team member's judgement. Nothing shows the post or link caused the enquiry, and ERPX never says that a post produced an enrolment.",
    "How far a lead got is its current status in the CRM: contacted or later, qualified or later, applied (an admission exists that isn't cancelled), enrolled (the lead is converted).",
    "Tracked-link opens are counts of visits, not people. They can include a few automated visits and are not matched to leads, so there is no click-to-enrolment rate.",
]
_CONTACTED = {LeadStatus.CONTACTED, LeadStatus.QUALIFIED, LeadStatus.CONVERTED}
_QUALIFIED = {LeadStatus.QUALIFIED, LeadStatus.CONVERTED}
STALE_NEW_DAYS = 2


def _start(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)


def _stage(rows: list[tuple[LeadLink, Lead, bool]]) -> dict:
    return {
        "leads": len(rows),
        "contacted": sum(1 for _, lead, _ in rows if lead.status in _CONTACTED),
        "qualified": sum(1 for _, lead, _ in rows if lead.status in _QUALIFIED),
        "applied": sum(1 for _, _, applied in rows if applied),
        "enrolled": sum(1 for _, lead, _ in rows if lead.status == LeadStatus.CONVERTED),
        "lost": sum(1 for _, lead, _ in rows if lead.status == LeadStatus.LOST),
    }


class AttributionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _linked(self, organization_id: uuid.UUID, start: date, end: date) -> list[tuple[LeadLink, Lead, bool]]:
        applied_ids = set((await self.db.execute(select(Admission.lead_id).where(Admission.organization_id == organization_id, Admission.status != AdmissionStatus.CANCELLED))).scalars())
        rows = (
            await self.db.execute(
                select(LeadLink, Lead)
                .join(Lead, Lead.id == LeadLink.lead_id)
                .where(LeadLink.organization_id == organization_id, Lead.deleted_at.is_(None), LeadLink.created_at >= _start(start), LeadLink.created_at < _start(end + timedelta(days=1)))
            )
        ).all()
        return [(link, lead, lead.id in applied_ids) for link, lead in rows]

    async def funnel(self, organization_id: uuid.UUID, start: date, end: date) -> dict:
        linked = await self._linked(organization_id, start, end)
        lo, hi = _start(start), _start(end + timedelta(days=1))
        comments = (
            await self.db.execute(
                select(func.count()).select_from(IgComment).where(
                    IgComment.organization_id == organization_id, IgComment.parent_external_id.is_(None), IgComment.is_own.is_(False), IgComment.category == "enquiry", IgComment.posted_at >= lo, IgComment.posted_at < hi
                )
            )
        ).scalar_one()
        conversations = (
            await self.db.execute(
                select(func.count()).select_from(IgConversation).where(IgConversation.organization_id == organization_id, IgConversation.category == "enquiry", IgConversation.last_user_message_at >= lo, IgConversation.last_user_message_at < hi)
            )
        ).scalar_one()
        media = {m.external_id: m for m in (await self.db.execute(select(IgMedia).where(IgMedia.organization_id == organization_id))).scalars()}
        posts = {p.id: p for p in (await self.db.execute(select(SocialPost).where(SocialPost.organization_id == organization_id))).scalars()}
        links = {l.id: l for l in (await self.db.execute(select(TrackedLink).where(TrackedLink.organization_id == organization_id))).scalars()}
        clicks = await LinkService(self.db).clicks_between(organization_id, start, end)

        def group(keyfn) -> dict:
            out: dict = defaultdict(list)
            for item in linked:
                key = keyfn(item[0])
                if key is not None:
                    out[key].append(item)
            return out

        by_post = []
        for key, rows in group(lambda l: l.media_external_id or (str(l.post_id) if l.post_id else None)).items():
            m = media.get(key)
            p = posts.get(rows[0][0].post_id) if rows[0][0].post_id else None
            by_post.append({"label": (p.title if p else None) or ((m.caption or "")[:80] if m else None) or "A post", "permalink": m.permalink if m else None, **_stage(rows)})
        by_link = []
        for key, rows in group(lambda l: l.link_id).items():
            link = links.get(key)
            by_link.append({"label": link.name if link else "A removed link", "placement": link.placement if link else None, "opens": clicks.get(key, 0), **_stage(rows)})
        for lid, link in links.items():  # a link with opens but no linked lead still belongs in the report
            if clicks.get(lid) and not any(r["label"] == link.name for r in by_link):
                by_link.append({"label": link.name, "placement": link.placement, "opens": clicks[lid], **_stage([])})
        by_course = [{"label": key, **_stage(rows)} for key, rows in group(lambda l: (l.course_label or "Not recorded")).items()]
        by_origin = [{"label": key, **_stage(rows)} for key, rows in group(lambda l: l.origin).items()]
        order = lambda r: (-r["leads"], r["label"])  # noqa: E731
        return {
            "period": {"start": start, "end": end},
            "enquiries_seen": {"comments": comments, "messages": conversations, "note": "Items the keyword rules labelled as enquiries. A rough pointer: some are not, and some real enquiries aren't caught."},
            "linked": _stage(linked),
            "by_post": sorted(by_post, key=order), "by_link": sorted(by_link, key=lambda r: (-r["leads"], -r["opens"], r["label"])),
            "by_course": sorted(by_course, key=order), "by_origin": sorted(by_origin, key=order),
            "assumptions": ASSUMPTIONS,
        }

    async def social_leads(self, organization_id: uuid.UUID, now: datetime | None = None, limit: int = 50) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        rows = (
            await self.db.execute(
                select(LeadLink, Lead).join(Lead, Lead.id == LeadLink.lead_id).where(LeadLink.organization_id == organization_id, Lead.deleted_at.is_(None)).order_by(LeadLink.created_at.desc()).limit(limit)
            )
        ).all()
        if not rows:
            return []
        lead_ids = [l.id for _, l in rows]
        follow = {}
        for lead_id, at in (
            await self.db.execute(select(FollowUp.lead_id, func.min(FollowUp.scheduled_at)).where(FollowUp.lead_id.in_(lead_ids), FollowUp.status == FollowUpStatus.SCHEDULED).group_by(FollowUp.lead_id))
        ).all():
            follow[lead_id] = at
        names = {i: n for i, n in (await self.db.execute(select(User.id, User.full_name).where(User.id.in_([l.assigned_to_user_id for _, l in rows if l.assigned_to_user_id])))).all()}
        out = []
        for link, lead in rows:
            at = follow.get(lead.id)
            open_lead = lead.status in (LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.QUALIFIED)
            if not open_lead:
                state = "closed"
            elif at is not None:
                state = "overdue" if at < now else "scheduled"
            else:
                state = "none"
            out.append(
                {
                    "lead_id": lead.id, "name": lead.full_name, "status": lead.status.value, "course": link.course_label, "handle": link.handle, "origin": link.origin, "created_at": link.created_at,
                    "assigned_to": names.get(lead.assigned_to_user_id), "next_follow_up_at": at, "follow_up": state, "basis": link.basis,
                    "needs_first_contact": lead.status == LeadStatus.NEW and (now - link.created_at) > timedelta(days=STALE_NEW_DAYS),
                }
            )
        return out

    async def attention(self, organization_id: uuid.UUID, now: datetime | None = None) -> dict:
        """Counts for the daily briefing: linked leads nobody has contacted, and follow-ups that are overdue."""
        leads = await self.social_leads(organization_id, now, 200)
        return {"needs_first_contact": sum(1 for l in leads if l["needs_first_contact"]), "overdue_follow_ups": sum(1 for l in leads if l["follow_up"] == "overdue")}
