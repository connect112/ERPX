"""
Media module — ORM models.

An `Album` is a named collection (e.g. "Hackathon 2026 Photos");
`MediaAsset` rows are the individual files inside it, uploaded through
the same two-phase presigned-URL flow as `modules.documents.Document` —
a `PENDING` row is created first, the browser uploads directly to MinIO,
then `POST /assets/{id}/confirm` verifies the object actually exists
before flipping it to `UPLOADED`. Kept as its own module (rather than
reusing Documents' generic `entity_type`/`entity_id` attachment) because
a gallery needs album grouping and captions, which the generic
attachment model has no concept of.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class MediaAssetStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Album(TimestampedBase):
    __tablename__ = "media_albums"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class MediaAsset(TimestampedBase):
    __tablename__ = "media_assets"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    album_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_albums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[MediaAssetStatus] = mapped_column(
        SAEnum(MediaAssetStatus, name="media_asset_status", values_callable=_values),
        default=MediaAssetStatus.PENDING,
        server_default=MediaAssetStatus.PENDING.value,
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
