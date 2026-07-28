import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.pentrix.challenges.models import Challenge  # noqa: F401
from modules.students.models import Student  # noqa: F401


class Hint(TimestampedBase):
    __tablename__ = "pentrix_hints"

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pentrix_challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    point_cost: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class HintUnlock(TimestampedBase):
    __tablename__ = "pentrix_hint_unlocks"
    __table_args__ = (UniqueConstraint("student_id", "hint_id", name="uq_hint_unlock"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pentrix_hints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
