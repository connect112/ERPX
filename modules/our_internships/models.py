"""
Our Internships -- Pentrix's own internship programmes, filled from the students of our institution events.

An internship picks the pool of students it may select from (one institution's event, one institution's events, or every
student we have registered) and keeps the shortlist ("selected students"). The performance shown while choosing is not
stored here: it is read from the event's exams and hackathons when asked for, so it is never out of date.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db.base_model import TimestampedBase
from modules.institutions import models as _institutions_models  # noqa: F401  (the foreign keys point at its tables)


def _values(enum_cls):
    return [m.value for m in enum_cls]


class InternshipScope(str, enum.Enum):
    INSTITUTION = "institution"
    ALL = "all"


class OurInternshipStatus(str, enum.Enum):
    SELECTING = "selecting"
    OFFERS_RELEASED = "offers_released"
    CLOSED = "closed"


class OfferStatus(str, enum.Enum):
    NOT_SENT = "not_sent"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class OurInternship(TimestampedBase):
    __tablename__ = "our_internships"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Who can be selected: students of one institution (optionally of one of its events), or every student.
    scope: Mapped[InternshipScope] = mapped_column(
        SAEnum(InternshipScope, name="our_internship_scope", values_callable=_values), nullable=False
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institution_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[OurInternshipStatus] = mapped_column(
        SAEnum(OurInternshipStatus, name="our_internship_status", values_callable=_values),
        default=OurInternshipStatus.SELECTING,
        server_default=OurInternshipStatus.SELECTING.value,
        nullable=False,
        index=True,
    )
    # The offer letter: the uploaded PDF template, where each field is printed on it, and the email that carries it.
    offer_template_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_template_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_template_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_template_data: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    offer_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    offer_email_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The date printed on the letters; empty means the day they are released.
    offer_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    offers_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InternshipSelection(TimestampedBase):
    """A student on an internship's shortlist."""

    __tablename__ = "our_internship_selections"
    __table_args__ = (UniqueConstraint("internship_id", "student_id", name="uq_internship_selection"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institution_students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The offer letter sent to this student.
    offer_reference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    offer_status: Mapped[OfferStatus] = mapped_column(
        SAEnum(OfferStatus, name="our_internship_offer_status", values_callable=_values),
        default=OfferStatus.NOT_SENT,
        server_default=OfferStatus.NOT_SENT.value,
        nullable=False,
    )
    offer_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    offer_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
