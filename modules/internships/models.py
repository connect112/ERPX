"""
Internships module — ORM models.

Reuses `modules.placements.Company` as the hiring/recruiting partner for
internship postings too, since a company that hires interns is the same
kind of external organization as one that posts full-time roles. An
`Internship` record is the active, in-progress engagement created once a
student's `InternshipApplication` is marked SELECTED — it tracks mentor
assignment and stipend separately from the posting defaults because those
can be negotiated per-student.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class InternshipPostingStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class InternshipApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    SELECTED = "selected"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class InternshipStatus(str, enum.Enum):
    ONGOING = "ongoing"
    COMPLETED = "completed"
    TERMINATED = "terminated"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class InternshipPosting(TimestampedBase):
    __tablename__ = "internship_postings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("placement_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stipend: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    required_skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[InternshipPostingStatus] = mapped_column(
        SAEnum(InternshipPostingStatus, name="internship_posting_status", values_callable=_values),
        default=InternshipPostingStatus.DRAFT,
        server_default=InternshipPostingStatus.DRAFT.value,
        nullable=False,
        index=True,
    )


class InternshipApplication(TimestampedBase):
    __tablename__ = "internship_applications"
    __table_args__ = (
        UniqueConstraint("internship_posting_id", "student_id", name="uq_internship_app_posting_student"),
    )

    internship_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[InternshipApplicationStatus] = mapped_column(
        SAEnum(InternshipApplicationStatus, name="internship_application_status", values_callable=_values),
        default=InternshipApplicationStatus.APPLIED,
        server_default=InternshipApplicationStatus.APPLIED.value,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Internship(TimestampedBase):
    __tablename__ = "internships"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_applications.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    internship_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mentor_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stipend: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[InternshipStatus] = mapped_column(
        SAEnum(InternshipStatus, name="internship_status", values_callable=_values),
        default=InternshipStatus.ONGOING,
        server_default=InternshipStatus.ONGOING.value,
        nullable=False,
        index=True,
    )
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
