"""Internship projects: what students choose, how they may hand it in, and what they handed in."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.internship_learning import models as _learning_models  # noqa: F401  (shares the file store)
from modules.our_internships import models as _internship_models  # noqa: F401  (the foreign keys point at its tables)


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class SubmissionMethod(str, enum.Enum):
    FILE = "file"
    EMAIL = "email"
    REPOSITORY = "repository"


class InternshipProject(TimestampedBase):
    """A project students can choose on an internship. Staff decide how it may be handed in: uploaded files, an email to a
    given address, a repository link, or any mix of these."""

    __tablename__ = "internship_projects"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The project's rules and what a good submission must contain.
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    submission_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"id", "title", "url"}]. Documents and templates are InternshipFile rows owned by the project.
    reference_links: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    allow_file: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    allow_email: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    allow_repository: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # Where students email their work when email submission is allowed.
    submission_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_files: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    # How many students may choose this project (empty: no limit).
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allow_late: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="internship_project_status", values_callable=_values),
        default=ProjectStatus.DRAFT,
        server_default=ProjectStatus.DRAFT.value,
        nullable=False,
        index=True,
    )


class ProjectChoice(TimestampedBase):
    """The project a student has chosen. A student holds one project per internship."""

    __tablename__ = "internship_project_choices"
    __table_args__ = (UniqueConstraint("internship_id", "selection_id", name="uq_project_choice_student"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chosen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProjectSubmission(TimestampedBase):
    """A student's hand-in for their project, and the record of how it arrived."""

    __tablename__ = "internship_project_submissions"
    __table_args__ = (UniqueConstraint("project_id", "selection_id", name="uq_project_submission"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[SubmissionMethod] = mapped_column(
        SAEnum(SubmissionMethod, name="internship_submission_method", values_callable=_values), nullable=False
    )
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    resubmission_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # For email submissions the work arrives outside the system; staff confirm once it has.
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
