"""
Our Internships -- Pentrix's own internship programmes, filled from the students of our institution events.

An internship picks the pool of students it may select from (one institution's event, one institution's events, or every
student we have registered) and keeps the shortlist ("selected students"). The performance shown while choosing is not
stored here: it is read from the event's exams and hackathons when asked for, so it is never out of date.
"""

import enum
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

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
