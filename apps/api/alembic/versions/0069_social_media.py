"""social media: settings, connected accounts and posts

Revision ID: 0069
Revises: 0068
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base() -> list:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _org() -> sa.Column:
    return sa.Column(
        "organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "social_settings",
        *_base(),
        _org(),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("publish_mode", sa.String(20), server_default="manual", nullable=False),
        sa.Column("brand", postgresql.JSONB(), nullable=False),
        sa.Column("pillars", postgresql.JSONB(), nullable=False),
        sa.Column("personas", postgresql.JSONB(), nullable=False),
        sa.Column("prohibited_claims", postgresql.JSONB(), nullable=False),
        sa.Column("objectives", postgresql.JSONB(), nullable=False),
        sa.Column("design_rules", postgresql.JSONB(), nullable=False),
        sa.Column("budgets", postgresql.JSONB(), nullable=False),
        sa.Column("notifications", postgresql.JSONB(), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default="365", nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_social_settings_org"),
    )
    op.create_table(
        "social_accounts",
        *_base(),
        _org(),
        sa.Column("platform", sa.String(20), server_default="instagram", nullable=False),
        sa.Column("external_account_id", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("account_type", sa.String(30), nullable=True),
        sa.Column("status", sa.String(20), server_default="connected", nullable=False),
        sa.Column("scopes", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.UniqueConstraint("organization_id", "platform", "external_account_id", name="uq_social_account"),
    )
    op.create_index("ix_social_accounts_organization_id", "social_accounts", ["organization_id"])
    op.create_table(
        "social_posts",
        *_base(),
        _org(),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("pillar", sa.String(50), nullable=True),
        sa.Column("objective", sa.String(300), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("content", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("sources", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("warnings", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("verification_status", sa.String(20), server_default="not_required", nullable=False),
        sa.Column("high_risk", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("time_sensitive", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_content_hash", sa.String(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_media_id", sa.String(100), nullable=True),
        sa.Column("external_permalink", sa.String(500), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_social_posts_idempotency_key"),
    )
    op.create_index("ix_social_posts_organization_id", "social_posts", ["organization_id"])
    op.create_index("ix_social_posts_campaign_id", "social_posts", ["campaign_id"])
    op.create_index("ix_social_posts_org_status", "social_posts", ["organization_id", "status"])
    op.create_index("ix_social_posts_status_scheduled", "social_posts", ["status", "scheduled_at"])


def downgrade() -> None:
    op.drop_table("social_posts")
    op.drop_table("social_accounts")
    op.drop_table("social_settings")
