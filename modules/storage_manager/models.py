"""
Storage Manager models: the Trash (files moved aside and recoverable) and the deletion log (append-only history).

Neither table ever holds a file's content. Trash points at a copy kept in object storage under `.trash/`, and the
log records who did what to which file and the dependency evidence that allowed it.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class StorageTrash(TimestampedBase):
    __tablename__ = "storage_trash"

    # Null for a file that belongs to no organization (platform-level files; superusers only).
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    original_key: Mapped[str] = mapped_column(String(700), nullable=False)
    trash_key: Mapped[str] = mapped_column(String(800), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    etag: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # What the dependency check found at the moment of deletion.
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StorageDeletionLog(TimestampedBase):
    """Append-only. Nothing in the API updates or deletes a row here."""

    __tablename__ = "storage_deletion_log"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # trash | restore | purge
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    object_key: Mapped[str] = mapped_column(String(800), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trash_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
