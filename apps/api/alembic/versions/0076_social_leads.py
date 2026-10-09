"""social media phase 5b: tracked links, daily click counts, lead links

Revision ID: 0076
Revises: 0075
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base() -> list:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _org() -> sa.Column:
    return sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)


def _fk(name: str, target: str, ondelete: str = "SET NULL", nullable: bool = True) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "social_links",
        *_base(),
        _org(),
        _fk("created_by_user_id", "users.id"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token", sa.String(20), nullable=False),
        sa.Column("destination", sa.String(500), nullable=False),
        sa.Column("placement", sa.String(20), server_default="other", nullable=False),
        _fk("post_id", "social_posts.id"),
        sa.Column("course_label", sa.String(255), nullable=True),
        _fk("marketing_campaign_id", "marketing_campaigns.id"),
        sa.Column("utm_campaign", sa.String(100), nullable=False),
        sa.Column("utm_content", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.UniqueConstraint("token", name="uq_social_links_token"),
    )
    op.create_index("ix_social_links_organization_id", "social_links", ["organization_id"])

    op.create_table(
        "social_link_days",
        *_base(),
        _fk("link_id", "social_links.id", ondelete="CASCADE", nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("link_id", "day", name="uq_social_link_day"),
    )
    op.create_index("ix_social_link_days_link_id", "social_link_days", ["link_id"])

    op.create_table(
        "social_lead_links",
        *_base(),
        _org(),
        _fk("lead_id", "crm_leads.id", ondelete="CASCADE", nullable=False),
        _fk("created_by_user_id", "users.id"),
        sa.Column("origin", sa.String(20), nullable=False),
        _fk("comment_id", "social_comments.id"),
        _fk("conversation_id", "social_conversations.id"),
        _fk("link_id", "social_links.id"),
        _fk("post_id", "social_posts.id"),
        sa.Column("media_external_id", sa.String(100), nullable=True),
        sa.Column("course_label", sa.String(255), nullable=True),
        sa.Column("handle", sa.String(100), nullable=True),
        sa.Column("basis", sa.String(400), nullable=False),
        sa.UniqueConstraint("lead_id", name="uq_social_lead_link_lead"),
        sa.UniqueConstraint("comment_id", name="uq_social_lead_link_comment"),
        sa.UniqueConstraint("conversation_id", name="uq_social_lead_link_conversation"),
    )
    op.create_index("ix_social_lead_links_organization_id", "social_lead_links", ["organization_id"])


def downgrade() -> None:
    for table in ("social_lead_links", "social_link_days", "social_links"):
        op.drop_table(table)
