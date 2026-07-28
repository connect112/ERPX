"""
Timetable module — ORM models.

A `TimetableEntry` is one recurring weekly slot in a `Batch`'s schedule
(e.g. "Mondays 10:00-12:00, Room A, with Trainer X") — the recurring
counterpart to Live Classes' one-off scheduled sessions.
"""

import enum
import uuid
from datetime import time

from sqlalchemy import ForeignKey, String, Time
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class DayOfWeek(str, enum.Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class TimetableEntry(TimestampedBase):
    __tablename__ = "timetable_entries"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True, index=True
    )
    trainer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    day_of_week: Mapped[DayOfWeek] = mapped_column(
        SAEnum(DayOfWeek, name="day_of_week", values_callable=_values), nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
