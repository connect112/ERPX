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

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
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
    """
    `source`/`external_id`/`source_url`/`last_seen_at`/`absence_streak` exist
    for the automated job-aggregation pipeline (`aggregation_service.py`) —
    every staff-created posting keeps `source="manual"` and never touches the
    other four fields, so nothing about the existing CRUD/self-service
    surface changes shape or behavior.

    The `(organization_id, source, external_id)` partial-unique index is the
    upsert key the pipeline dedupes against per source, per organization —
    it's partial (`source IS NOT NULL AND external_id IS NOT NULL`) rather
    than a plain composite unique constraint mostly for self-documentation:
    `external_id` is NULL for every manual posting, and Postgres already
    treats each NULL as distinct in an ordinary unique index, so a plain
    index would behave the same in practice. The explicit WHERE clause makes
    that intent legible to a future reader instead of relying on that
    Postgres NULL-handling detail being remembered.
    """

    __tablename__ = "placement_job_postings"
    __table_args__ = (
        Index(
            "uq_placement_job_postings_org_source_external_id",
            "organization_id",
            "source",
            "external_id",
            unique=True,
            postgresql_where=text("source IS NOT NULL AND external_id IS NOT NULL"),
        ),
    )

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
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual", server_default="manual", index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    absence_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class JobPostingMatch(TimestampedBase):
    """
    Links two `JobPosting` rows the aggregation pipeline's dedup step
    (`aggregation_service.py::_dedupe`) determined are the same real-world
    posting appearing on different sources. `duplicate_posting_id` stays a
    full, independently-queryable `JobPosting` — its own `source`/
    `source_url`/`external_id` are preserved for attribution — it's simply
    excluded from the default student/staff listing once matched, in favor
    of `canonical_posting_id`.
    """

    __tablename__ = "placement_job_posting_matches"
    __table_args__ = (
        UniqueConstraint(
            "canonical_posting_id", "duplicate_posting_id", name="uq_job_posting_match_pair"
        ),
    )

    canonical_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("placement_job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    duplicate_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("placement_job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    similarity_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    matched_fields: Mapped[str | None] = mapped_column(Text, nullable=True)


class AggregationRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED_NO_AI = "skipped_no_ai"


class AggregationRun(TimestampedBase):
    """
    One row per hourly (or manually-triggered, or weekly Jooble-only) pull
    of the job-aggregation pipeline. Not organization-scoped — like
    `modules.backups.models.BackupJob`, the run itself is a whole-platform
    operation even though its output (`JobPosting` rows) fans out per
    organization; see `AggregationRunSource` for the per-connector detail
    this run-level row can't express on its own.
    """

    __tablename__ = "placements_aggregation_runs"

    triggered_by: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AggregationRunStatus] = mapped_column(
        SAEnum(AggregationRunStatus, name="placements_aggregation_run_status", values_callable=_values),
        default=AggregationRunStatus.QUEUED,
        server_default=AggregationRunStatus.QUEUED.value,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    postings_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    postings_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    postings_closed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    matches_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AggregationRunSource(TimestampedBase):
    """
    Per-connector outcome for one `AggregationRun` — the whole reason this
    is a separate table (not a JSON column on `AggregationRun`) is so
    per-source failures stay individually queryable/filterable, and so
    `request_count` can be summed with a plain `SELECT SUM(...)` for the
    Adzuna daily-budget and Jooble lifetime-budget checks in
    `connectors/adzuna.py` / `connectors/jooble.py`.
    """

    __tablename__ = "placements_aggregation_run_sources"

    aggregation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("placements_aggregation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    postings_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


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
