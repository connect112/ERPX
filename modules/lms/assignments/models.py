import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.models import Course  # noqa: F401
from modules.students.models import Student  # noqa: F401


class SubmissionStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    GRADED = "graded"
    LATE = "late"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Assignment(TimestampedBase):
    __tablename__ = "lms_assignments"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_score: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)


class AssignmentSubmission(TimestampedBase):
    __tablename__ = "lms_assignment_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_submission_assignment_student"),
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lms_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, name="submission_status", values_callable=_values),
        default=SubmissionStatus.SUBMITTED,
        server_default=SubmissionStatus.SUBMITTED.value,
        nullable=False,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
