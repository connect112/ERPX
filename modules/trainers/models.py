"""
Trainers module — ORM models.

A `Trainer` is a teaching-specific profile layered on top of an existing
`Employee` record (specializations, bio, weekly-hours cap) rather than a
competing person-record with its own name/contact/address columns —
that data already lives on `Employee` and duplicating it here would
violate normalization for no benefit. Batches, Timetable, and Live
Classes all reference `Trainer`, not `Employee`, directly.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class Trainer(TimestampedBase):
    __tablename__ = "trainers"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    specializations: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_weekly_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
