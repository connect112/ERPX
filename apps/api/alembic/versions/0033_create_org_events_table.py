"""create org_events table

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

event_type_enum = postgresql.ENUM("holiday", "meeting", "announcement", "other", name="org_event_type")

_ALL_ENUMS = [event_type_enum]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "org_events",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "event_type", postgresql.ENUM("holiday", "meeting", "announcement", "other", name="org_event_type", create_type=False),
            nullable=False, server_default="other",
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_org_events_organization_id", "org_events", ["organization_id"])
    op.create_index("ix_org_events_event_type", "org_events", ["event_type"])
    op.create_index("ix_org_events_start_at", "org_events", ["start_at"])


def downgrade() -> None:
    op.drop_table("org_events")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
