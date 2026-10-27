"""
Internship learning: the work students do once they are enrolled on an internship -- assignments now, projects, reviews and
certificates in later steps. Everything hangs off ``our_internships`` and is keyed by the student's selection on it, so
submissions, marks and files always belong to the right internship and the right student.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.our_internships import models as _internship_models  # noqa: F401  (the foreign keys point at its tables)


def _values(enum_cls):
    return [m.value for m in enum_cls]


class AssignmentStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class InternshipFile(TimestampedBase):
    """A file kept in object storage and attached to something in an internship (an assignment's reference material, a
    student's submission, later a project's documents). One table for all of them; ``owner_type`` + ``owner_id`` say what
    it belongs to."""

    __tablename__ = "internship_files"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_type: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(600), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class InternshipAssignment(TimestampedBase):
    __tablename__ = "internship_assignments"

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
    # The questions or tasks: [{"id", "title", "details"}]
    tasks: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    # [{"id", "criterion", "points"}]: what staff mark a submission on. Empty means one free score out of max_marks.
    rubric: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allow_late: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    max_files: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="internship_assignment_status", values_callable=_values),
        default=AssignmentStatus.DRAFT,
        server_default=AssignmentStatus.DRAFT.value,
        nullable=False,
        index=True,
    )


class AssignmentSubmission(TimestampedBase):
    """A student's work on one assignment, and the marks and feedback it received."""

    __tablename__ = "internship_assignment_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "selection_id", name="uq_assignment_submission"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    resubmission_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # {rubric rule id: marks awarded}; ``score`` is their sum (or the free score when the assignment has no rubric).
    rubric_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
