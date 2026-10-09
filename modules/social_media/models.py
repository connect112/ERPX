"""
Social Media module: ORM models.

`SocialSettings` is one row per organisation (brand, content strategy, publishing policy, budgets).
`SocialAccount` is a connected social account (Instagram first); its access token is only ever stored encrypted and is
never returned by the API. `SocialPost` is a piece of content with its approval and publishing state.

Changes to these tables are recorded by the application-wide audit hooks (modules.audit); the token column is excluded.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.marketing.campaigns.models import Campaign  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # The publish request may or may not have reached Instagram: it is checked against the account, never blindly retried.
    PUBLISH_UNKNOWN = "publish_unknown"


class PostFormat(str, enum.Enum):
    IMAGE = "image"
    CAROUSEL = "carousel"
    REEL = "reel"
    STORY = "story"


class VerificationStatus(str, enum.Enum):
    NOT_REQUIRED = "not_required"  # no factual or time-sensitive claims
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    CONFLICTING = "conflicting"
    OUTDATED = "outdated"


class SocialSettings(TimestampedBase):
    __tablename__ = "social_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    # "manual": approved posts are published by an admin's click. "scheduled": at their scheduled time.
    publish_mode: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual", nullable=False)
    brand: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pillars: Mapped[list] = mapped_column(JSONB, nullable=False)
    personas: Mapped[list] = mapped_column(JSONB, nullable=False)
    prohibited_claims: Mapped[list] = mapped_column(JSONB, nullable=False)
    objectives: Mapped[list] = mapped_column(JSONB, nullable=False)
    design_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    budgets: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notifications: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=365, server_default="365", nullable=False)


class SocialAccount(TimestampedBase):
    __tablename__ = "social_accounts"
    __audit_exclude_fields__ = {"token_encrypted"}
    __table_args__ = (UniqueConstraint("organization_id", "platform", "external_account_id", name="uq_social_account"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), default="instagram", server_default="instagram", nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # not_connected | connected | expiring | expired | revoked | error
    status: Mapped[str] = mapped_column(String(20), default="connected", server_default="connected", nullable=False)
    scopes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    # {capability key: "available" | "needs_app_review" | "unavailable" | "unknown"} found when connecting.
    capabilities: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SocialPost(TimestampedBase):
    __tablename__ = "social_posts"
    __table_args__ = (
        Index("ix_social_posts_org_status", "organization_id", "status"),
        Index("ix_social_posts_status_scheduled", "status", "scheduled_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_posts.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    format: Mapped[str] = mapped_column(String(20), default=PostFormat.IMAGE.value, nullable=False)
    pillar: Mapped[str | None] = mapped_column(String(50), nullable=True)
    objective: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=PostStatus.DRAFT.value, nullable=False)

    # hooks, headline, caption, cta, hashtags, alt_text, thumbnail_text, visual_direction, slides (see schemas.PostContent)
    content: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # [{"url", "title", "published_at", "retrieved_at"}]: where the factual claims come from
    sources: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    # [{"severity": "info" | "warning" | "blocking", "message"}]: unresolved verification or quality problems
    warnings: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(20), default=VerificationStatus.NOT_REQUIRED.value, server_default="not_required", nullable=False
    )
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    time_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Hash of exactly what was approved. Publishing refuses a post whose content no longer matches it.
    approved_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_media_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_permalink: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # One per post, so a publish retried after an unclear outcome can be matched to the original attempt.
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
