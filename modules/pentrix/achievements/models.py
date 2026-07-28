import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401
from modules.students.models import Student  # noqa: F401


class AchievementCriteriaType(str, enum.Enum):
    CHALLENGES_SOLVED = "challenges_solved"  # criteria_value = number of solves
    POINTS_THRESHOLD = "points_threshold"  # criteria_value = total points earned


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Achievement(TimestampedBase):
    __tablename__ = "pentrix_achievements"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria_type: Mapped[AchievementCriteriaType] = mapped_column(
        SAEnum(AchievementCriteriaType, name="achievement_criteria_type", values_callable=_values),
        nullable=False,
    )
    criteria_value: Mapped[int] = mapped_column(Integer, nullable=False)


class StudentAchievement(TimestampedBase):
    __tablename__ = "pentrix_student_achievements"
    __table_args__ = (
        UniqueConstraint("student_id", "achievement_id", name="uq_student_achievement"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pentrix_achievements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
