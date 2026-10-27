"""Instructors assigned to an internship, each with an access window."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.our_internships import models as _internship_models  # noqa: F401  (the foreign key points at its table)
from modules.trainers import models as _trainer_models  # noqa: F401  (likewise)


class InternshipInstructor(TimestampedBase):
    """A trainer who may work on one internship (students, exams, assignments, projects, reviews, awards, certificates...)
    from ``access_from`` until ``access_until``. An empty start means from now; an empty end means until removed. Outside
    the window the internship is invisible to them. One row per trainer per internship; change the dates to extend or
    shorten the access."""

    __tablename__ = "internship_instructors"
    __table_args__ = (UniqueConstraint("internship_id", "trainer_id", name="uq_internship_instructor"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trainer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False, index=True)
    access_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
