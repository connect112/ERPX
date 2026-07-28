"""add backup_jobs.sha256 and create restore_attempts table

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

restore_status_enum = postgresql.ENUM(
    "dry_run", "succeeded", "failed", "aborted", name="restore_attempt_status"
)

_ALL_ENUMS = [restore_status_enum]


def upgrade() -> None:
    op.add_column("backup_jobs", sa.Column("sha256", sa.String(length=64), nullable=True))

    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    # Best-effort audit trail for apps/api/scripts/restore_backup.py — the
    # script's *primary* audit trail is a local structured log file (always
    # written, regardless of target database state); this table is a
    # queryable secondary record, only ever written to as the very last
    # step of a restore attempt (after the target is confirmed reachable
    # and migrated), never a precondition for the restore itself.
    # `backup_job_id` is nullable (SET NULL) rather than a hard FK
    # requirement: an operator can point the script at a raw local .sql
    # file with no corresponding BackupJob row at all.
    op.create_table(
        "restore_attempts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("backup_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("backup_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("initiated_by", sa.String(length=255), nullable=False),
        sa.Column("target_database", sa.String(length=255), nullable=False),
        sa.Column(
            "status", postgresql.ENUM("dry_run", "succeeded", "failed", "aborted", name="restore_attempt_status", create_type=False),
            nullable=False,
        ),
        sa.Column("safety_backup_path", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_restore_attempts_status", "restore_attempts", ["status"])


def downgrade() -> None:
    op.drop_table("restore_attempts")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
    op.drop_column("backup_jobs", "sha256")
