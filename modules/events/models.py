"""
Events module — org-wide calendar.

Ad-hoc, org-scoped calendar entries (holidays, all-hands meetings,
general announcements) that don't belong to any single business
module — distinct from Batches' class schedule, Timetable's recurring
periods, Live Classes' sessions, or Alumni's reunion events, all of
which already have their own date fields tied to a specific domain
record. This is the one place for "the org has a holiday on the 15th."
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class EventType(str, enum.Enum):
    HOLIDAY = "holiday"
    MEETING = "meeting"
    ANNOUNCEMENT = "announcement"
    OTHER = "other"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Event(TimestampedBase):
    __tablename__ = "org_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType, name="org_event_type", values_callable=_values),
        default=EventType.OTHER,
        server_default=EventType.OTHER.value,
        nullable=False,
        index=True,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
