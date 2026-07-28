import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401


class LabDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    INSANE = "insane"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Lab(TimestampedBase):
    __tablename__ = "pentrix_labs"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_lab_org_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[LabDifficulty] = mapped_column(
        SAEnum(LabDifficulty, name="lab_difficulty", values_callable=_values),
        default=LabDifficulty.EASY,
        server_default=LabDifficulty.EASY.value,
        nullable=False,
    )
    # Reference to the container/VM image the provisioner should launch.
    # This module never talks to Docker/a hypervisor directly — see
    # pentrix/lab_instances/provisioning.py for the pluggable abstraction.
    environment_image: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    default_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=60, server_default="60", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
