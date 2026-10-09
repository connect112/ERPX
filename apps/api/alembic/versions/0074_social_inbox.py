"""social media phase 4b: Instagram media, comments, conversations, messages and replies

Revision ID: 0074
Revises: 0073
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0074"
down_revision: Union[str, None] = "0073"
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


def _triage() -> list:
    return [
        sa.Column("category", sa.String(30), server_default="other", nullable=False),
        sa.Column("priority", sa.String(10), server_default="low", nullable=False),
        sa.Column("needs_care", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("care_reason", sa.String(200), nullable=True),
        sa.Column("summary", sa.String(400), nullable=True),
        sa.Column("suggested_reply", sa.Text(), nullable=True),
        sa.Column("suggestion_note", sa.String(300), nullable=True),
        sa.Column("suggestion_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "social_ig_media",
        *_base(),
        _org(),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("media_type", sa.String(30), nullable=True),
        sa.Column("product_type", sa.String(30), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("permalink", sa.String(500), nullable=True),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_social_ig_media"),
    )
    op.create_index("ix_social_ig_media_organization_id", "social_ig_media", ["organization_id"])

    op.create_table(
        "social_comments",
        *_base(),
        _org(),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("media_external_id", sa.String(100), nullable=True),
        sa.Column("parent_external_id", sa.String(100), nullable=True),
        sa.Column("text", sa.Text(), server_default="", nullable=False),
        sa.Column("author_username", sa.String(100), nullable=True),
        sa.Column("author_id", sa.String(100), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_own", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(20), server_default="new", nullable=False),
        *_triage(),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_social_comment"),
    )
    op.create_index("ix_social_comments_organization_id", "social_comments", ["organization_id"])
    op.create_index("ix_social_comments_org_status", "social_comments", ["organization_id", "status"])
    op.create_index("ix_social_comments_org_posted", "social_comments", ["organization_id", "posted_at"])

    op.create_table(
        "social_conversations",
        *_base(),
        _org(),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("participant_id", sa.String(100), nullable=True),
        sa.Column("participant_username", sa.String(100), nullable=True),
        sa.Column("remote_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_user_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_from_us", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        *_triage(),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_social_conversation"),
    )
    op.create_index("ix_social_conversations_organization_id", "social_conversations", ["organization_id"])
    op.create_index("ix_social_conversations_org_status", "social_conversations", ["organization_id", "status"])

    op.create_table(
        "social_messages",
        *_base(),
        _org(),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("direction", sa.String(3), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_social_message"),
    )
    op.create_index("ix_social_messages_organization_id", "social_messages", ["organization_id"])
    op.create_index("ix_social_messages_conversation", "social_messages", ["conversation_id", "sent_at"])

    op.create_table(
        "social_replies",
        *_base(),
        _org(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_comments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_external_id", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(25), server_default="typed", nullable=False),
        sa.Column("acknowledged_sensitive", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(10), server_default="pending", nullable=False),
        sa.Column("external_reply_id", sa.String(200), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "request_id", name="uq_social_reply_request"),
    )
    op.create_index("ix_social_replies_organization_id", "social_replies", ["organization_id"])
    op.create_index("ix_social_replies_org_created", "social_replies", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_table("social_replies")
    op.drop_table("social_messages")
    op.drop_table("social_conversations")
    op.drop_table("social_comments")
    op.drop_table("social_ig_media")
