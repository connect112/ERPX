"""
LMS / Assessments — ORM models.

Consolidates the spec's `quizzes/`, `mock-tests/`, and `coding-tests/`
folders into one `Assessment` table distinguished by `assessment_type`,
for the same reason Resources consolidated videos/notes/downloads: the
three would otherwise be near-identical (title, course, scoring,
duration). Per-question data modeling belongs to the Examinations
module's question-bank (built next); this table is the LMS-side
container plus each student's attempt/score record.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.models import Course  # noqa: F401
from modules.students.models import Student  # noqa: F401


class AssessmentType(str, enum.Enum):
    QUIZ = "quiz"
    MOCK_TEST = "mock_test"
    CODING_TEST = "coding_test"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Assessment(TimestampedBase):
    __tablename__ = "lms_assessments"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    assessment_type: Mapped[AssessmentType] = mapped_column(
        SAEnum(AssessmentType, name="assessment_type", values_callable=_values),
        default=AssessmentType.QUIZ,
        server_default=AssessmentType.QUIZ.value,
        nullable=False,
    )
    total_marks: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    passing_marks: Mapped[int] = mapped_column(Integer, default=40, server_default="40", nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AssessmentAttempt(TimestampedBase):
    __tablename__ = "lms_assessment_attempts"
    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", name="uq_attempt_assessment_student"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lms_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AttemptStatus] = mapped_column(
        SAEnum(AttemptStatus, name="attempt_status", values_callable=_values),
        default=AttemptStatus.IN_PROGRESS,
        server_default=AttemptStatus.IN_PROGRESS.value,
        nullable=False,
    )
