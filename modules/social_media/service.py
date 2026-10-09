"""
Social Media module: settings, posts and their approval workflow, and the overview.

The workflow is deliberately strict. A post only reaches `approved` through an explicit approval by someone allowed to
approve, with its warnings acknowledged; the approval records exactly what was approved (a content hash); any later
edit withdraws it. The states a post reaches by being published (`scheduled`, `publishing`, `published`, `failed`,
`publish_unknown`) can't be set from here at all: only the publisher (a later phase) moves a post into them.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from modules.crm.leads.models import Lead, LeadSource
from modules.social_media import defaults
from modules.social_media.models import (
    PostFormat,
    PostStatus,
    SocialAccount,
    SocialPost,
    SocialSettings,
    VerificationStatus,
)
from modules.social_media.schemas import (
    CAROUSEL_MAX,
    CAROUSEL_MIN,
    BriefingItem,
    LeadSummary,
    PostContent,
    PostCreate,
    PostPublic,
    PostTransition,
    PostUpdate,
    RoadmapItem,
    SettingsUpdate,
)

# Once a post is on its way to (or already on) Instagram its content is frozen.
LOCKED = {
    PostStatus.SCHEDULED.value,
    PostStatus.PUBLISHING.value,
    PostStatus.PUBLISHED.value,
    PostStatus.PUBLISH_UNKNOWN.value,
}
# What a person may do to a post, by its current status.
TRANSITIONS: dict[str, dict[str, str]] = {
    "submit": {PostStatus.DRAFT.value: PostStatus.REVIEW.value},
    "request_changes": {PostStatus.REVIEW.value: PostStatus.DRAFT.value},
    "approve": {PostStatus.REVIEW.value: PostStatus.APPROVED.value},
    "unapprove": {PostStatus.APPROVED.value: PostStatus.DRAFT.value},
    "cancel": {
        PostStatus.DRAFT.value: PostStatus.CANCELLED.value,
        PostStatus.REVIEW.value: PostStatus.CANCELLED.value,
        PostStatus.APPROVED.value: PostStatus.CANCELLED.value,
        PostStatus.FAILED.value: PostStatus.CANCELLED.value,
    },
    "reopen": {PostStatus.CANCELLED.value: PostStatus.DRAFT.value, PostStatus.FAILED.value: PostStatus.DRAFT.value},
}


def content_hash(post: SocialPost) -> str:
    """A fingerprint of everything that would be published, so approval can be tied to exactly that."""
    payload = {
        "format": post.format,
        "content": post.content,
        "sources": post.sources,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class SettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, organization_id: uuid.UUID) -> SocialSettings:
        row = (
            await self.db.execute(select(SocialSettings).where(SocialSettings.organization_id == organization_id))
        ).scalar_one_or_none()
        if row is None:
            row = SocialSettings(
                organization_id=organization_id,
                timezone=defaults.DEFAULT_TIMEZONE,
                publish_mode="manual",
                brand=defaults.DEFAULT_BRAND,
                pillars=defaults.DEFAULT_PILLARS,
                personas=defaults.DEFAULT_PERSONAS,
                prohibited_claims=defaults.DEFAULT_PROHIBITED_CLAIMS,
                objectives=defaults.DEFAULT_OBJECTIVES,
                design_rules=defaults.DEFAULT_DESIGN_RULES,
                budgets=defaults.DEFAULT_BUDGETS,
                notifications=defaults.DEFAULT_NOTIFICATIONS,
            )
            self.db.add(row)
            await self.db.flush()
        return row

    async def update(self, organization_id: uuid.UUID, payload: SettingsUpdate) -> SocialSettings:
        row = await self.get(organization_id)
        for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
            if value is None:
                continue
            setattr(row, field, value)
        await self.db.flush()
        return row


class PostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- reading ----------------

    async def get(self, post_id: uuid.UUID, organization_id: uuid.UUID) -> SocialPost:
        post = (
            await self.db.execute(
                select(SocialPost).where(SocialPost.id == post_id, SocialPost.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if post is None:
            raise NotFoundError("Post not found.")
        return post

    async def list(
        self,
        organization_id: uuid.UUID,
        status: str | None = None,
        pillar: str | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[SocialPost], int]:
        conditions = [SocialPost.organization_id == organization_id]
        if status:
            conditions.append(SocialPost.status == status)
        if pillar:
            conditions.append(SocialPost.pillar == pillar)
        if q:
            conditions.append(SocialPost.title.ilike(f"%{q.strip()[:100]}%"))
        total = (await self.db.execute(select(func.count()).select_from(SocialPost).where(*conditions))).scalar_one()
        rows = (
            await self.db.execute(
                select(SocialPost).where(*conditions).order_by(SocialPost.updated_at.desc()).offset(skip).limit(limit)
            )
        ).scalars()
        return list(rows), total

    # ---------------- helpers ----------------

    async def _local_time(self, organization_id: uuid.UUID, value: datetime | None) -> datetime | None:
        """A time typed without a timezone means the organisation's own (account) timezone."""
        if value is None or value.tzinfo is not None:
            return value
        zone = ZoneInfo((await SettingsService(self.db).get(organization_id)).timezone)
        return value.replace(tzinfo=zone)

    @staticmethod
    def _check_content(format: str, content: dict) -> None:
        slides = content.get("slides") or []
        if format == PostFormat.CAROUSEL.value and slides and not (CAROUSEL_MIN <= len(slides) <= CAROUSEL_MAX):
            raise ValidationError(f"A carousel has {CAROUSEL_MIN} to {CAROUSEL_MAX} slides.")

    # ---------------- changes ----------------

    async def create(self, organization_id: uuid.UUID, user_id: uuid.UUID, payload: PostCreate) -> SocialPost:
        data = payload.model_dump(mode="json")
        self._check_content(payload.format.value, data["content"])
        post = SocialPost(
            organization_id=organization_id,
            created_by_user_id=user_id,
            status=PostStatus.DRAFT.value,
            title=payload.title.strip(),
            format=payload.format.value,
            pillar=payload.pillar,
            objective=payload.objective,
            campaign_id=payload.campaign_id,
            content=data["content"],
            sources=data["sources"],
            verification_status=payload.verification_status.value,
            high_risk=payload.high_risk,
            time_sensitive=payload.time_sensitive,
            scheduled_at=await self._local_time(organization_id, payload.scheduled_at),
        )
        self.db.add(post)
        await self.db.flush()
        return post

    async def update(self, post: SocialPost, payload: PostUpdate) -> bool:
        """Returns True when this edit withdrew an earlier approval."""
        if post.status in LOCKED:
            raise ConflictError("This post is scheduled or published, so it can't be edited. Cancel the schedule first.")
        if post.status == PostStatus.CANCELLED.value:
            raise ConflictError("This post is cancelled. Reopen it to edit it.")
        data = payload.model_dump(exclude_unset=True, mode="json")
        content_changed = False
        for field in ("title", "pillar", "objective", "campaign_id", "high_risk", "time_sensitive"):
            if field in data and (data[field] is not None or field in ("pillar", "objective", "campaign_id")):
                value = data[field]
                setattr(post, field, uuid.UUID(value) if field == "campaign_id" and value else value)
        if "format" in data and data["format"]:
            content_changed |= data["format"] != post.format
            post.format = data["format"]
        if "content" in data and data["content"] is not None:
            self._check_content(post.format, data["content"])
            content_changed |= data["content"] != post.content
            post.content = data["content"]
        if "sources" in data and data["sources"] is not None:
            content_changed |= data["sources"] != post.sources
            post.sources = data["sources"]
        if "verification_status" in data and data["verification_status"]:
            post.verification_status = data["verification_status"]
        if payload.clear_schedule:
            content_changed |= post.scheduled_at is not None
            post.scheduled_at = None
        elif "scheduled_at" in data and payload.scheduled_at is not None:
            when = await self._local_time(post.organization_id, payload.scheduled_at)
            content_changed |= when != post.scheduled_at
            post.scheduled_at = when
        withdrawn = False
        if post.status == PostStatus.APPROVED.value and content_changed:
            # What was approved is no longer what is saved: it has to be reviewed again.
            post.status = PostStatus.DRAFT.value
            post.approved_by_user_id = None
            post.approved_at = None
            post.approved_content_hash = None
            withdrawn = True
        await self.db.flush()
        await self.db.refresh(post)  # updated_at is set by the database
        return withdrawn

    async def duplicate(self, post: SocialPost, user_id: uuid.UUID) -> SocialPost:
        copy = SocialPost(
            organization_id=post.organization_id,
            created_by_user_id=user_id,
            duplicate_of_id=post.id,
            status=PostStatus.DRAFT.value,
            title=f"{post.title} (copy)"[:200],
            format=post.format,
            pillar=post.pillar,
            objective=post.objective,
            campaign_id=post.campaign_id,
            content=json.loads(json.dumps(post.content)),
            sources=json.loads(json.dumps(post.sources)),
            # A copy has to be verified again: the original's check does not carry over.
            verification_status=(
                VerificationStatus.UNVERIFIED.value
                if post.verification_status != VerificationStatus.NOT_REQUIRED.value
                else post.verification_status
            ),
            high_risk=post.high_risk,
            time_sensitive=post.time_sensitive,
        )
        self.db.add(copy)
        await self.db.flush()
        return copy

    async def delete(self, post: SocialPost) -> None:
        if post.status not in (PostStatus.DRAFT.value, PostStatus.CANCELLED.value):
            raise ConflictError("Only drafts and cancelled posts can be deleted. Cancel this post instead.")
        await self.db.delete(post)
        await self.db.flush()

    async def transition(self, post: SocialPost, payload: PostTransition, user_id: uuid.UUID, can_approve: bool) -> SocialPost:
        action = payload.action
        target = TRANSITIONS[action].get(post.status)
        if target is None:
            raise ConflictError(f"A post that is {post.status.replace('_', ' ')} can't be changed that way.")
        if action in ("approve", "unapprove") and not can_approve:
            raise AuthorizationError("Approving posts needs the social_media.approve permission.")
        if action == "approve":
            self._check_can_approve(post, payload)
            post.approved_by_user_id = user_id
            post.approved_at = datetime.now(timezone.utc)
            post.approved_content_hash = content_hash(post)
        elif action != "submit":
            post.approved_by_user_id = None
            post.approved_at = None
            post.approved_content_hash = None
        post.status = target
        await self.db.flush()
        await self.db.refresh(post)
        return post

    @staticmethod
    def _check_can_approve(post: SocialPost, payload: PostTransition) -> None:
        content = post.content or {}
        if not (content.get("caption") or "").strip():
            raise ValidationError("Write a caption before approving this post.")
        if post.format == PostFormat.CAROUSEL.value:
            count = len(content.get("slides") or [])
            if not (CAROUSEL_MIN <= count <= CAROUSEL_MAX):
                raise ValidationError(f"A carousel needs {CAROUSEL_MIN} to {CAROUSEL_MAX} slides before it can be approved.")
        if post.verification_status in (VerificationStatus.CONFLICTING.value, VerificationStatus.OUTDATED.value):
            raise ValidationError(
                f"This post's claims are marked {post.verification_status}. Fix or remove them before approving."
            )
        if post.verification_status == VerificationStatus.UNVERIFIED.value:
            raise ValidationError("This post makes factual claims that haven't been verified yet. Check them against the sources first.")
        if post.verification_status == VerificationStatus.VERIFIED.value and not post.sources:
            raise ValidationError("A verified post needs its sources listed.")
        blocking = [w for w in (post.warnings or []) if w.get("severity") == "blocking"]
        if blocking:
            raise ValidationError(f"Resolve the blocking warning first: {blocking[0].get('message', '')}")
        if (post.warnings or []) and not payload.acknowledge_warnings:
            raise ValidationError("This post has warnings. Read them and confirm you have reviewed them to approve.")
        if (post.high_risk or post.time_sensitive) and not payload.acknowledge_high_risk:
            raise ValidationError(
                "This post makes high-risk or time-sensitive security claims. Confirm that you have checked them "
                "against the sources yourself to approve."
            )

    @staticmethod
    def public(post: SocialPost, approval_withdrawn: bool = False) -> PostPublic:
        out = PostPublic.model_validate(post)
        out.approval_withdrawn = approval_withdrawn
        return out


class OverviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def post_counts(self, organization_id: uuid.UUID) -> dict[str, int]:
        rows = await self.db.execute(
            select(SocialPost.status, func.count())
            .where(SocialPost.organization_id == organization_id)
            .group_by(SocialPost.status)
        )
        counts = {status.value: 0 for status in PostStatus}
        counts.update({status: count for status, count in rows.all()})
        return counts

    async def account(self, organization_id: uuid.UUID) -> SocialAccount | None:
        return (
            await self.db.execute(
                select(SocialAccount)
                .where(SocialAccount.organization_id == organization_id, SocialAccount.platform == "instagram")
                .order_by(SocialAccount.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def leads(self, organization_id: uuid.UUID) -> LeadSummary:
        """Leads the CRM has recorded with source "Social media". Their link to a specific post comes with Phase 5."""
        since = datetime.now(timezone.utc) - timedelta(days=30)
        rows = await self.db.execute(
            select(Lead.status, func.count())
            .where(
                Lead.organization_id == organization_id,
                Lead.source == LeadSource.SOCIAL_MEDIA,
                Lead.deleted_at.is_(None),
                Lead.created_at >= since,
            )
            .group_by(Lead.status)
        )
        by_status = {status.value: count for status, count in rows.all()}
        return LeadSummary(
            last_30_days=sum(by_status.values()),
            by_status=by_status,
            note=(
                "Leads the CRM has marked as coming from social media. They are not yet linked to individual posts: "
                "that attribution arrives with Phase 5, and no enrolment is credited to a post without evidence."
            ),
        )

    async def briefing(
        self, counts: dict[str, int], connected: bool, settings: SocialSettings, leads: LeadSummary
    ) -> list[BriefingItem]:
        items: list[BriefingItem] = []
        if counts.get("publish_unknown"):
            items.append(BriefingItem(level="warning", message=f"{counts['publish_unknown']} post(s) have an unclear publishing outcome and need checking."))
        if counts.get("failed"):
            items.append(BriefingItem(level="warning", message=f"{counts['failed']} post(s) failed to publish."))
        if counts.get("review"):
            items.append(BriefingItem(level="action", message=f"{counts['review']} post(s) are waiting for your approval.", link="posts?status=review"))
        if not connected:
            items.append(
                BriefingItem(
                    level="info",
                    message="Instagram isn't connected yet. Comments, messages, publishing and insights need the connection (Phase 4).",
                    link="settings",
                )
            )
        if not settings.brand.get("colors_confirmed"):
            items.append(BriefingItem(level="info", message="The brand colours are placeholders. Confirm your approved palette under Strategy.", link="strategy"))
        if not settings.brand.get("logo_key"):
            items.append(BriefingItem(level="info", message="No approved logo is uploaded yet. Artwork needs it (Phase 2).", link="strategy"))
        if not settings.notifications.get("emails"):
            items.append(BriefingItem(level="info", message="No notification email is set, so failures won't be emailed.", link="settings"))
        if leads.last_30_days:
            items.append(BriefingItem(level="info", message=f"{leads.last_30_days} CRM lead(s) in the last 30 days came from social media."))
        if not items:
            items.append(BriefingItem(level="info", message="Nothing needs attention right now."))
        return items

    @staticmethod
    def roadmap() -> list[RoadmapItem]:
        return [RoadmapItem(**item) for item in defaults.ROADMAP]
