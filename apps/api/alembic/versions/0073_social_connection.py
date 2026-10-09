"""social media phase 4a: account connection state and webhook events

Revision ID: 0073
Revises: 0072
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0073"
down_revision: Union[str, None] = "0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_settings", sa.Column("connect_state", postgresql.JSONB(), server_default="{}", nullable=False))
    op.add_column("social_accounts", sa.Column("sync_state", postgresql.JSONB(), server_default="{}", nullable=False))
    op.create_table(
        "social_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("entry_id", sa.String(100), nullable=False),
        sa.Column("field", sa.String(60), nullable=False),
        sa.Column("object_id", sa.String(200), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("event_hash", name="uq_social_webhook_events_hash"),
    )
    op.create_index("ix_social_webhook_events_organization_id", "social_webhook_events", ["organization_id"])


def downgrade() -> None:
    op.drop_table("social_webhook_events")
    op.drop_column("social_accounts", "sync_state")
    op.drop_column("social_settings", "connect_state")
