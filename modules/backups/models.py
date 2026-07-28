"""
Backups module — real `pg_dump` snapshots of the whole database.

Deliberately not organization-scoped like most models here: every
organization's data lives in the same shared Postgres database (this
platform is multi-tenant at the row level, not the database level), so
a "backup" is inherently a whole-database operation. Access is gated by
the `backups.manage`/`backups.view` permissions instead, which
`SYSTEM_ROLES` in `modules.authorization.service` deliberately does NOT
grant to the default "Staff" role — only Administrator/Super Admin can
trigger or download a full database dump.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class BackupStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RestoreAttemptStatus(str, enum.Enum):
    DRY_RUN = "dry_run"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class BackupJob(TimestampedBase):
    __tablename__ = "backup_jobs"

    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[BackupStatus] = mapped_column(
        SAEnum(BackupStatus, name="backup_status", values_callable=_values),
        default=BackupStatus.PENDING,
        server_default=BackupStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # SHA-256 of the dump file, computed at backup time before upload — lets
    # apps/api/scripts/restore_backup.py verify the downloaded file wasn't
    # corrupted or tampered with before replaying it. Nullable: backups
    # created before this column existed have no checksum to compare
    # against, not a data-loss condition.
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RestoreAttempt(TimestampedBase):
    """
    Best-effort, queryable secondary audit trail for
    apps/api/scripts/restore_backup.py — the script's primary audit trail
    is a local structured log file, written unconditionally regardless of
    target database state (a restore can target a database that doesn't
    have this table yet). A row here is only ever written as the final
    step of an already-completed (successful, failed, or deliberately
    aborted) attempt against a database that does have this table.

    Not exposed via any API route — this finding is explicitly CLI-only,
    manual, confirmation-gated. `initiated_by` is free text (an operator
    identifier the script's caller supplies), not a `users.id` FK: the
    target database may not even have a `users` table populated yet
    (a fresh disaster-recovery restore) when this row is written.
    """

    __tablename__ = "restore_attempts"

    backup_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backup_jobs.id", ondelete="SET NULL"), nullable=True
    )
    initiated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    target_database: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[RestoreAttemptStatus] = mapped_column(
        SAEnum(RestoreAttemptStatus, name="restore_attempt_status", values_callable=_values),
        nullable=False,
        index=True,
    )
    safety_backup_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
