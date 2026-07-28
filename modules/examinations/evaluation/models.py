import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.examinations.exams.models import Exam  # noqa: F401
from modules.examinations.question_bank.models import Question  # noqa: F401
from modules.students.models import Student  # noqa: F401


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ExamAttempt(TimestampedBase):
    __tablename__ = "exam_attempts"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_exam_attempt_student"),)

    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AttemptStatus] = mapped_column(
        SAEnum(AttemptStatus, name="exam_attempt_status", values_callable=_values),
        default=AttemptStatus.IN_PROGRESS,
        server_default=AttemptStatus.IN_PROGRESS.value,
        nullable=False,
    )


class ExamAnswer(TimestampedBase):
    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),)

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_questions_bank.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    marks_awarded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
