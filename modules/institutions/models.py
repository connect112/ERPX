"""
Institutions module -- the colleges we partner with, the events (workshops, hackathons, exams) held at them, and the
students who registered for those events.

Three ideas keep the records tidy:

* A student is one row per institution (``InstitutionStudent``), found by email. The same person attending a workshop and
  then a hackathon is still one person, so correcting a name or email once corrects it everywhere.
* Being registered for an event is its own row (``EventRegistration``). Uploading a list to one event registers those
  people for that event only; it never adds them to another event or institution.
* An exam or a hackathon belongs to an event through a nullable ``event_id`` on its own table, so it is a single record
  that can be managed from its own module or from the event page, never copied.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db.base_model import TimestampedBase


def _values(enum_cls):
    return [m.value for m in enum_cls]


class InstitutionEventType(str, enum.Enum):
    WORKSHOP = "workshop"
    HACKATHON = "hackathon"
    EXAM = "exam"
    OTHER = "other"


class InstitutionEventStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"


class Institution(TimestampedBase):
    __tablename__ = "institutions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The city or place the institution is in.
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    # The MOU: free text, and/or an uploaded document (kept in the database, like other small uploads here).
    mou_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    mou_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mou_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mou_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mou_data: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    # The faculty member who contacted us or coordinates with us.
    faculty_name: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    faculty_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    faculty_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InstitutionEvent(TimestampedBase):
    __tablename__ = "institution_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[InstitutionEventType] = mapped_column(
        SAEnum(InstitutionEventType, name="institution_event_type", values_callable=_values),
        default=InstitutionEventType.WORKSHOP,
        server_default=InstitutionEventType.WORKSHOP.value,
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional ceiling on registrations; None means no limit.
    max_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[InstitutionEventStatus] = mapped_column(
        SAEnum(InstitutionEventStatus, name="institution_event_status", values_callable=_values),
        default=InstitutionEventStatus.UPCOMING,
        server_default=InstitutionEventStatus.UPCOMING.value,
        nullable=False,
        index=True,
    )


class InstitutionStudent(TimestampedBase):
    """A student of one institution. Matched across lists, exams and hackathons by (lower-cased) email."""

    __tablename__ = "institution_students"
    __table_args__ = (UniqueConstraint("institution_id", "email", name="uq_institution_student_email"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Always stored lower-cased -- the unique constraint above relies on it.
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Whatever else the registration list had (roll number, department, year...), keyed by the column's name.
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)


class EventRegistration(TimestampedBase):
    """A student registered for one event, with that event's individual score and remarks (entered by staff)."""

    __tablename__ = "institution_event_students"
    __table_args__ = (UniqueConstraint("event_id", "student_id", name="uq_event_registration"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institution_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institution_students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    individual_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
