import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.chapters.models import Chapter  # noqa: F401


class LessonContentType(str, enum.Enum):
    VIDEO = "video"
    TEXT = "text"
    DOCUMENT = "document"
    QUIZ = "quiz"


class Lesson(TimestampedBase):
    __tablename__ = "course_lessons"
    __table_args__ = (UniqueConstraint("chapter_id", "order_index", name="uq_lesson_chapter_order"),)

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[LessonContentType] = mapped_column(
        SAEnum(
            LessonContentType,
            name="lesson_content_type",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        default=LessonContentType.VIDEO,
        server_default=LessonContentType.VIDEO.value,
        nullable=False,
    )
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_preview: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
