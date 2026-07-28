"""
Courses module — root ORM model.

`Course` is the top-level content entity. Chapters (courses/chapters)
nest under it, Lessons (courses/lessons) nest under Chapters, and
Resources (courses/resources — covering downloadable videos, notes,
and files in one table via a `resource_type` field rather than three
near-identical tables) attach to Lessons. Learning Paths
(courses/learning_paths) group multiple Courses into a guided sequence.
"""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import SoftDeleteMixin, TimestampedBase
from modules.courses.categories.models import Category  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class CourseLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Course(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_course_org_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    level: Mapped[CourseLevel] = mapped_column(
        SAEnum(CourseLevel, name="course_level", values_callable=_values),
        default=CourseLevel.BEGINNER,
        server_default=CourseLevel.BEGINNER.value,
        nullable=False,
    )
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
