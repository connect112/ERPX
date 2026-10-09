"""social media phase 2a: research items, AI usage, generation record

Revision ID: 0070
Revises: 0069
Create Date: 2026-10-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0070"
down_revision: Union[str, None] = "0069"
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
        "social_research_items",
        *_base(),
        _org(),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("url", sa.String(600), nullable=False),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("cve_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("facts", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("flags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("status", sa.String(20), server_default="new", nullable=False),
        sa.UniqueConstraint("organization_id", "source", "external_id", name="uq_social_research_item"),
    )
    op.create_index("ix_social_research_org_published", "social_research_items", ["organization_id", "published_at"])
    op.create_table(
        "social_ai_usage",
        *_base(),
        _org(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("est_cost_inr", sa.Numeric(12, 4), server_default="0", nullable=False),
    )
    op.create_index("ix_social_ai_usage_org_created", "social_ai_usage", ["organization_id", "created_at"])
    op.add_column("social_posts", sa.Column("generation", postgresql.JSONB(), server_default="{}", nullable=False))
    op.add_column("social_settings", sa.Column("research_state", postgresql.JSONB(), server_default="{}", nullable=False))


def downgrade() -> None:
    op.drop_column("social_settings", "research_state")
    op.drop_column("social_posts", "generation")
    op.drop_table("social_ai_usage")
    op.drop_table("social_research_items")
