import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401
from modules.pentrix.labs.models import Lab, LabDifficulty  # noqa: F401


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Challenge(TimestampedBase):
    __tablename__ = "pentrix_challenges"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # A challenge can stand alone (CTF-style, no environment) or be tied
    # to a Lab whose environment it's solved inside.
    lab_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pentrix_labs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[LabDifficulty] = mapped_column(
        SAEnum(LabDifficulty, name="lab_difficulty", values_callable=_values),
        default=LabDifficulty.EASY,
        server_default=LabDifficulty.EASY.value,
        nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
