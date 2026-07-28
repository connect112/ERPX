import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.lessons.models import Lesson  # noqa: F401
from modules.students.models import Student  # noqa: F401


class LessonBookmark(TimestampedBase):
    __tablename__ = "lms_lesson_bookmarks"
    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_bookmark_student_lesson"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
