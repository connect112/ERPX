"""
Live Classes module — ORM models.

A `LiveClass` is a single scheduled virtual session for a `Batch` — the
one-off counterpart to Timetable's recurring weekly slots (e.g. a
one-time doubt-clearing session, or a guest lecture, alongside the
regular weekly schedule).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class LiveClassStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class LiveClass(TimestampedBase):
    __tablename__ = "live_classes"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trainer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60", nullable=False)
    meeting_link: Mapped[str] = mapped_column(String(512), nullable=False)
    recording_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[LiveClassStatus] = mapped_column(
        SAEnum(LiveClassStatus, name="live_class_status", values_callable=_values),
        default=LiveClassStatus.SCHEDULED,
        server_default=LiveClassStatus.SCHEDULED.value,
        nullable=False,
        index=True,
    )
    # Set the first time the trainer actually mints a join-token for this
    # class (see get_live_class_join_token_as_trainer) -- students can't
    # get their own join-token until this is set, so they never land in
    # an empty room before the trainer has actually shown up, regardless
    # of how early status flips to LIVE. Never cleared once set -- a
    # trainer's later disconnect doesn't re-lock the room for everyone
    # else already in it.
    trainer_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
