import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.courses.models import Course  # noqa: F401
from modules.students.models import Student  # noqa: F401


class VivaExam(TimestampedBase):
    __tablename__ = "exam_vivas"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    panel_members: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_marks: Mapped[int] = mapped_column(Integer, default=50, server_default="50", nullable=False)
    passing_marks: Mapped[int] = mapped_column(Integer, default=20, server_default="20", nullable=False)


class VivaResult(TimestampedBase):
    __tablename__ = "exam_viva_results"
    __table_args__ = (UniqueConstraint("viva_id", "student_id", name="uq_viva_result_student"),)

    viva_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_vivas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
