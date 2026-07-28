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
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
