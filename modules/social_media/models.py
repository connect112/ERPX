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

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
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
    # {source: {"last_fetch_at", "ok", "error", "count"}}: when each research source was last read and how it went.
    research_state: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # A connection in progress: {"nonce", "user_id", "expires"}. One at a time, and a nonce can be used once.
    connect_state: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)


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
    # {"token": {"refreshed_at", ...}, "comments": {...}, "messages": {...}}: when things were last read and how it went.
    sync_state: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)


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
    # How an AI draft was made: model, the research items used, suggested time and its basis, hashtag basis.
    generation: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # What the artwork should look like: template, picture, headline overrides (see schemas.Design).
    # When the publisher may try again after a transient failure (None = as soon as it is due).
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When a publisher claimed the post (status "publishing"). A claim that goes stale means a crash or restart.
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    design: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # What was rendered from it: files, validation, metrics and the fingerprint of the text and design they show.
    artwork: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)


class ResearchItem(TimestampedBase):
    """Something found on an official source (a CISA advisory, a CISA known-exploited entry, an NVD record). It is the
    cache of what the research found, with where it came from and when it was retrieved."""

    __tablename__ = "social_research_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "source", "external_id", name="uq_social_research_item"),
        Index("ix_social_research_org_published", "organization_id", "published_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # cisa_kev | cisa_advisory | nvd
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(600), nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cve_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    # What the source states (vendor, product, CVSS, due date, ransomware use ...), kept as data, never as instructions.
    facts: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # Problems with the item itself, e.g. text that looks like an instruction to an AI.
    flags: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="new", server_default="new", nullable=False)  # new | used | dismissed


class AIUsage(TimestampedBase):
    """One paid AI call, with an estimated cost, so the monthly budget can be enforced and shown."""

    __tablename__ = "social_ai_usage"
    __table_args__ = (Index("ix_social_ai_usage_org_created", "organization_id", "created_at"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("social_posts.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # draft | regenerate | proofread | image
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    est_cost_inr: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"), server_default="0", nullable=False)


class SocialAsset(TimestampedBase):
    """An image the artwork can use: the approved logo, a photo, a lab screenshot, or an AI-generated background.
    `synthetic` is true for anything an image model made, and is never presented as genuine evidence."""

    __tablename__ = "social_assets"
    __table_args__ = (Index("ix_social_assets_org_kind", "organization_id", "kind"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # logo | photo | screenshot | background
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    alt_text: Mapped[str] = mapped_column(String(420), default="", server_default="", nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # For a generated background: the prompt and model used.
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)


class PublishAttempt(TimestampedBase):
    """One try at publishing a post: the record that makes duplicates preventable and an unclear outcome checkable.
    `publish_started_at` is set (and committed) just before the one call that actually creates the Instagram post, so a
    crash after it is known to be an *unknown* outcome that has to be checked, while a crash before it is safe to retry."""

    __tablename__ = "social_publish_attempts"
    __table_args__ = (Index("ix_social_publish_attempts_post", "post_id", "attempt_no"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False)
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # started | retry | published | failed | unknown | paused
    status: Mapped[str] = mapped_column(String(20), default="started", server_default="started", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # Instagram container ids made for this post (children first), reused by a retry while they are still valid.
    container_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    creation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publish_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    media_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    caption: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    error_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error: Mapped[str | None] = mapped_column(String(600), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WebhookEvent(TimestampedBase):
    """One notification from Meta, kept just long enough to ignore a retry of it. It holds ids only, never message text."""

    __tablename__ = "social_webhook_events"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    entry_id: Mapped[str] = mapped_column(String(100), nullable=False)
    field: Mapped[str] = mapped_column(String(60), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IgMedia(TimestampedBase):
    """A post on the Instagram profile, as Instagram reports it. Comments hang off these. When ERPX published it,
    `post_id` points at the ERPX post (and its artwork is used as the thumbnail)."""

    __tablename__ = "social_ig_media"
    __table_args__ = (UniqueConstraint("organization_id", "external_id", name="uq_social_ig_media"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("social_posts.id", ondelete="SET NULL"), nullable=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comments_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IgComment(TimestampedBase):
    """A comment on one of the account's posts. Its text is untrusted: it is shown escaped, fenced when given to an AI, and
    never acted on. `status` is what a person (or a reply of ours) has done with it, not what an AI thinks."""

    __tablename__ = "social_comments"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_social_comment"),
        Index("ix_social_comments_org_status", "organization_id", "status"),
        Index("ix_social_comments_org_posted", "organization_id", "posted_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    media_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    author_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_own: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    hidden: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # new | answered | ignored
    status: Mapped[str] = mapped_column(String(20), default="new", server_default="new", nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="other", server_default="other", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="low", server_default="low", nullable=False)
    needs_care: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    care_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # What an AI suggested (never sent): a short summary and a possible reply for a person to read, edit or ignore.
    summary: Mapped[str | None] = mapped_column(String(400), nullable=True)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    suggestion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IgConversation(TimestampedBase):
    """One person's direct-message conversation with the account (Instagram doesn't expose group chats or read state)."""

    __tablename__ = "social_conversations"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_social_conversation"),
        Index("ix_social_conversations_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    participant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    participant_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Instagram only lets the account reply for 24 hours after the person's last message.
    last_user_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_from_us: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # open (their message is the latest) | answered | ignored
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open", nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="other", server_default="other", nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="low", server_default="low", nullable=False)
    needs_care: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    care_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(400), nullable=True)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    suggestion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IgMessage(TimestampedBase):
    __tablename__ = "social_messages"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="uq_social_message"),
        Index("ix_social_messages_conversation", "conversation_id", "sent_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("social_conversations.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    direction: Mapped[str] = mapped_column(String(3), nullable=False)  # in | out
    text: Mapped[str | None] = mapped_column(Text, nullable=True)  # None for attachments, stickers and shares
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SocialReply(TimestampedBase):
    """The audit record of one reply a person chose to send: who, exactly what text, where it came from (typed, or an AI
    suggestion edited or not), what they acknowledged, and what Instagram answered. Nothing sends a reply without a row
    made by an explicit action first, and the row is written before the send is attempted."""

    __tablename__ = "social_replies"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_id", name="uq_social_reply_request"),
        Index("ix_social_replies_org_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Made by the browser once per dialog, so a double click or a retried request can't send twice.
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # comment | dm
    comment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("social_comments.id", ondelete="SET NULL"), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("social_conversations.id", ondelete="SET NULL"), nullable=True)
    target_external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # typed | suggestion_edited | suggestion_unchanged
    source: Mapped[str] = mapped_column(String(25), default="typed", server_default="typed", nullable=False)
    acknowledged_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # pending (about to be sent) | sent | failed (certainly not sent) | unknown (may or may not have gone out)
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending", nullable=False)
    external_reply_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
