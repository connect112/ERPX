import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.models import Course  # noqa: F401
from modules.students.models import Student  # noqa: F401


class Certificate(TimestampedBase):
    __tablename__ = "lms_certificates"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_certificate_student_course"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    certificate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
