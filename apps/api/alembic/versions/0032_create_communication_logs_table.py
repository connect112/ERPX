"""create communication_logs table

Revision ID: 0032
Revises: 0031
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

channel_enum = postgresql.ENUM("email", "sms", "whatsapp", name="communication_channel")
status_enum = postgresql.ENUM("sent", "failed", name="communication_status")

_ALL_ENUMS = [channel_enum, status_enum]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "communication_logs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "channel", postgresql.ENUM("email", "sms", "whatsapp", name="communication_channel", create_type=False),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status", postgresql.ENUM("sent", "failed", name="communication_status", create_type=False),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("related_entity_type", sa.String(length=100), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_communication_logs_organization_id", "communication_logs", ["organization_id"])
    op.create_index("ix_communication_logs_channel", "communication_logs", ["channel"])
    op.create_index("ix_communication_logs_status", "communication_logs", ["status"])
    op.create_index("ix_communication_logs_related_entity_type", "communication_logs", ["related_entity_type"])


def downgrade() -> None:
    op.drop_table("communication_logs")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
