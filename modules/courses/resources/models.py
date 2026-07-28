"""
Resources sub-module — ORM models.

Consolidates the spec's separate `videos/`, `notes/`, and `downloads/`
folders into a single `Resource` table distinguished by `resource_type`.
A dedicated video/note/download table each would be near-identical
(title, file/url, lesson_id) — one typed table is more maintainable and
still satisfies every one of those use cases via `resource_type`.
"""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.lessons.models import Lesson  # noqa: F401


class ResourceType(str, enum.Enum):
    VIDEO = "video"
    NOTE = "note"
    PDF = "pdf"
    DOCUMENT = "document"
    LINK = "link"
    OTHER = "other"


class Resource(TimestampedBase):
    __tablename__ = "course_resources"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[ResourceType] = mapped_column(
        SAEnum(
            ResourceType,
            name="resource_type",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        default=ResourceType.OTHER,
        server_default=ResourceType.OTHER.value,
        nullable=False,
    )
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_downloadable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
