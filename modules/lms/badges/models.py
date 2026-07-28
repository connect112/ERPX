import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401
from modules.students.models import Student  # noqa: F401


class Badge(TimestampedBase):
    __tablename__ = "lms_badges"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(512), nullable=True)


class StudentBadge(TimestampedBase):
    __tablename__ = "lms_student_badges"
    __table_args__ = (UniqueConstraint("student_id", "badge_id", name="uq_student_badge"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lms_badges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
