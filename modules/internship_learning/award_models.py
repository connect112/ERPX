"""Awards for an internship: staff define them (Best Project, Top Performer, ...) and give them to enrolled students."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.our_internships import models as _internship_models  # noqa: F401  (the foreign keys point at its tables)


class InternshipAward(TimestampedBase):
    __tablename__ = "internship_awards"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class AwardGrant(TimestampedBase):
    """An award given to one student."""

    __tablename__ = "internship_award_grants"
    __table_args__ = (UniqueConstraint("award_id", "selection_id", name="uq_award_grant"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    award_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("internship_awards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
