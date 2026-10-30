"""
Bulk download jobs.

One row per requested ZIP. It records who asked for which documents (the ids, fixed when the job is created, after the
permission check), how they were to be named, how far the job got, which documents failed and why, and where the
finished ZIP is kept until it expires. The row stays after the ZIP is removed, as the record of what was exported.

Create, status changes and downloads reach the audit trail through the usual hooks (modules/audit/hooks.py); the
progress counters and the id list are left out of it, so a 2,000-document job is one audit row, not 2,000.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class ExportStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


ACTIVE = (ExportStatus.QUEUED.value, ExportStatus.RUNNING.value)


class BulkExportJob(TimestampedBase):
    __tablename__ = "bulk_export_jobs"
    __table_args__ = (Index("ix_bulk_export_jobs_user_created", "requested_by_user_id", "created_at"),)
    __audit_exclude_fields__ = {"item_ids", "processed_items", "failed_items", "failures", "updated_at"}

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scope_label: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ExportStatus.QUEUED.value, nullable=False, index=True)
    # "selected" (ids picked by hand) or "filtered" (everything matching the filters, minus any left out)
    selection_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    item_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    # {"filename_template", "folder_template", "zip_template"}
    options: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    processed_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    failed_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # [{"id", "title", "error"}], capped (see service.MAX_FAILURES_KEPT)
    failures: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    zip_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(700), nullable=True, unique=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
