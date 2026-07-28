"""
Documents module — ORM models.

A generic, polymorphic file-attachment mechanism any module can use by
storing an `entity_type` (a table name, matching the convention
`modules.audit.hooks` already uses) and `entity_id` pointing at whatever
record the file belongs to — a corporate client, a course resource, an
HR record, etc. — without every module needing its own upload plumbing
or a migration adding a `*_url` column.

Upload is two-phase to avoid ever recording a document that doesn't
actually exist in object storage:
  1. `POST /documents/presigned-upload` creates a `PENDING` row and hands
     back a short-lived presigned PUT URL; the browser uploads directly
     to MinIO/S3, never through this API process.
  2. `POST /documents/{id}/confirm` verifies the object is really there
     (`StorageClient.object_exists`) before flipping the row to
     `UPLOADED`. A document that never gets confirmed (upload abandoned,
     failed, etc.) stays `PENDING` and is invisible to normal listing.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Document(TimestampedBase):
    __tablename__ = "documents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", values_callable=_values),
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
