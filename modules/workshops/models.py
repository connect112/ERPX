"""
Workshops module — ORM models.

A `Workshop` is a short, standalone training event (a few hours to a few
days) distinct from a `Course` — it doesn't have chapters/lessons/
progress tracking, just a schedule and a capacity. Registration is open
to both enrolled students and the public (walk-in leads), so
`WorkshopRegistration.student_id` is nullable and contact fields carry
the registrant's details when there's no student record to point to —
the same pattern `SupportTicket.raised_by_contact_name` uses for
external contacts.
"""

import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class WorkshopMode(str, enum.Enum):
    PHYSICAL = "physical"
    VIRTUAL = "virtual"


class WorkshopStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RegistrationStatus(str, enum.Enum):
    REGISTERED = "registered"
    ATTENDED = "attended"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Workshop(TimestampedBase):
    __tablename__ = "workshops"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_workshop_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    trainer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trainers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[WorkshopMode] = mapped_column(
        SAEnum(WorkshopMode, name="workshop_mode", values_callable=_values),
        default=WorkshopMode.PHYSICAL,
        server_default=WorkshopMode.PHYSICAL.value,
        nullable=False,
    )
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meeting_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    workshop_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0, server_default="0", nullable=False)
    status: Mapped[WorkshopStatus] = mapped_column(
        SAEnum(WorkshopStatus, name="workshop_status", values_callable=_values),
        default=WorkshopStatus.DRAFT,
        server_default=WorkshopStatus.DRAFT.value,
        nullable=False,
        index=True,
    )


class WorkshopRegistration(TimestampedBase):
    __tablename__ = "workshop_registrations"
    __table_args__ = (
        UniqueConstraint("workshop_id", "student_id", name="uq_workshop_registration_student"),
    )

    workshop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )

    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[RegistrationStatus] = mapped_column(
        SAEnum(RegistrationStatus, name="workshop_registration_status", values_callable=_values),
        default=RegistrationStatus.REGISTERED,
        server_default=RegistrationStatus.REGISTERED.value,
        nullable=False,
        index=True,
    )
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
