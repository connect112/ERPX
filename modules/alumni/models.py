"""
Alumni module — ORM models.

An `AlumniProfile` is created by a student themselves (self-service) once
they want to be listed as an alumnus — it is not auto-created on
graduation, since not every graduate wants a public alumni presence.
`is_verified` lets staff flag genuine profiles for public display without
gating profile creation itself behind approval.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class EventMode(str, enum.Enum):
    PHYSICAL = "physical"
    VIRTUAL = "virtual"


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RegistrationStatus(str, enum.Enum):
    REGISTERED = "registered"
    ATTENDED = "attended"
    CANCELLED = "cancelled"


class ReferralStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class AlumniProfile(TimestampedBase):
    __tablename__ = "alumni_profiles"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


class AlumniEvent(TimestampedBase):
    __tablename__ = "alumni_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[EventMode] = mapped_column(
        SAEnum(EventMode, name="alumni_event_mode", values_callable=_values),
        default=EventMode.VIRTUAL,
        server_default=EventMode.VIRTUAL.value,
        nullable=False,
    )
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    registration_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, name="alumni_event_status", values_callable=_values),
        default=EventStatus.DRAFT,
        server_default=EventStatus.DRAFT.value,
        nullable=False,
        index=True,
    )


class EventRegistration(TimestampedBase):
    __tablename__ = "alumni_event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "alumni_id", name="uq_alumni_event_registration"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alumni_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alumni_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alumni_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[RegistrationStatus] = mapped_column(
        SAEnum(RegistrationStatus, name="alumni_registration_status", values_callable=_values),
        default=RegistrationStatus.REGISTERED,
        server_default=RegistrationStatus.REGISTERED.value,
        nullable=False,
        index=True,
    )


class JobReferral(TimestampedBase):
    __tablename__ = "alumni_job_referrals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alumni_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alumni_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referral_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(ReferralStatus, name="alumni_referral_status", values_callable=_values),
        default=ReferralStatus.OPEN,
        server_default=ReferralStatus.OPEN.value,
        nullable=False,
        index=True,
    )
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
