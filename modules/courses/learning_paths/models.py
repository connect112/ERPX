import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.courses.models import Course  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class LearningPath(TimestampedBase):
    __tablename__ = "course_learning_paths"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_learning_path_org_slug"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningPathCourse(TimestampedBase):
    __tablename__ = "course_learning_path_courses"
    __table_args__ = (
        UniqueConstraint("learning_path_id", "course_id", name="uq_learning_path_course"),
        UniqueConstraint("learning_path_id", "order_index", name="uq_learning_path_order"),
    )

    learning_path_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_learning_paths.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
