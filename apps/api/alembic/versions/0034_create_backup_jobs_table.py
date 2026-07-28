"""create backup_jobs table

Revision ID: 0034
Revises: 0033
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

status_enum = postgresql.ENUM("pending", "running", "completed", "failed", name="backup_status")

_ALL_ENUMS = [status_enum]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "backup_jobs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("triggered_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("pending", "running", "completed", "failed", name="backup_status", create_type=False),
            nullable=False, server_default="pending",
        ),
        sa.Column("storage_key", sa.String(length=512), nullable=True, unique=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backup_jobs_status", "backup_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("backup_jobs")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
