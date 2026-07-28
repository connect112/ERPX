import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.models import Course  # noqa: F401
from modules.examinations.question_bank.models import Question  # noqa: F401


class ExamStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Exam(TimestampedBase):
    __tablename__ = "exam_exams"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60", nullable=False)
    passing_marks: Mapped[int] = mapped_column(Integer, default=40, server_default="40", nullable=False)
    status: Mapped[ExamStatus] = mapped_column(
        SAEnum(ExamStatus, name="exam_status", values_callable=_values),
        default=ExamStatus.DRAFT,
        server_default=ExamStatus.DRAFT.value,
        nullable=False,
    )


class ExamQuestion(TimestampedBase):
    __tablename__ = "exam_exam_questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "question_id", name="uq_exam_question"),
        UniqueConstraint("exam_id", "order_index", name="uq_exam_question_order"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_exams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_questions_bank.id", ondelete="CASCADE"), nullable=False, index=True
    )
    marks_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
