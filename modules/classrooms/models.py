"""
Classrooms module — ORM models.

A `Classroom` is a bookable teaching space, physical (a room at a
branch) or virtual (a standing meeting room), that Timetable entries
and Live Classes schedule sessions into.
"""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class ClassroomType(str, enum.Enum):
    PHYSICAL = "physical"
    VIRTUAL = "virtual"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Classroom(TimestampedBase):
    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_classroom_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    classroom_type: Mapped[ClassroomType] = mapped_column(
        SAEnum(ClassroomType, name="classroom_type", values_callable=_values),
        default=ClassroomType.PHYSICAL,
        server_default=ClassroomType.PHYSICAL.value,
        nullable=False,
    )
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meeting_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
