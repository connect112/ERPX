"""social media phase 3: publish attempts and scheduling columns

Revision ID: 0072
Revises: 0071
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0072"
down_revision: Union[str, None] = "0071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_posts", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("social_posts", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "social_publish_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="started", nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("container_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("creation_id", sa.String(100), nullable=True),
        sa.Column("publish_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("media_id", sa.String(100), nullable=True),
        sa.Column("caption", sa.Text(), server_default="", nullable=False),
        sa.Column("error_kind", sa.String(20), nullable=True),
        sa.Column("error", sa.String(600), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
    )
    op.create_index("ix_social_publish_attempts_organization_id", "social_publish_attempts", ["organization_id"])
    op.create_index("ix_social_publish_attempts_post", "social_publish_attempts", ["post_id", "attempt_no"])
    op.create_index("ix_social_posts_due", "social_posts", ["status", "scheduled_at", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_social_posts_due", table_name="social_posts")
    op.drop_table("social_publish_attempts")
    op.drop_column("social_posts", "claimed_at")
    op.drop_column("social_posts", "next_attempt_at")
