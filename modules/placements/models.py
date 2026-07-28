"""
Placements module — ORM models.

`Company` here is a hiring/recruiting partner, distinct from
`modules.corporate.clients.Client` (GIR's own B2B service clients) even
though both are "external organization" records — a company hiring
graduates has nothing to do with VAPT/SOC/AMC engagements, so folding
them into Client would conflate two unrelated relationships.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import SoftDeleteMixin, TimestampedBase


class JobType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"


class JobPostingStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    OFFERED = "offered"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Company(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "placement_companies"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_person_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobPosting(TimestampedBase):
    __tablename__ = "placement_job_postings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("placement_companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, name="placement_job_type", values_callable=_values),
        default=JobType.FULL_TIME,
        server_default=JobType.FULL_TIME.value,
        nullable=False,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    required_skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[JobPostingStatus] = mapped_column(
        SAEnum(JobPostingStatus, name="placement_job_posting_status", values_callable=_values),
        default=JobPostingStatus.DRAFT,
        server_default=JobPostingStatus.DRAFT.value,
        nullable=False,
        index=True,
    )


class Application(TimestampedBase):
    __tablename__ = "placement_applications"
    __table_args__ = (
        UniqueConstraint("job_posting_id", "student_id", name="uq_application_posting_student"),
    )

    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("placement_job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus, name="placement_application_status", values_callable=_values),
        default=ApplicationStatus.APPLIED,
        server_default=ApplicationStatus.APPLIED.value,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
