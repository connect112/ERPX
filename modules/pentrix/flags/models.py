"""
Pentrix / Flags — ORM models.

Flags are stored as SHA-256 hashes, never plaintext — the same principle
as password storage, applied here because a flag is a shared secret an
attacker (or a curious student poking at the database) shouldn't be able
to read directly. `Submission` records only successful solves (one per
student per challenge); incorrect attempts are verified in-memory and
don't need their own row, matching how CTF platforms typically track
solves rather than every attempt.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.pentrix.challenges.models import Challenge  # noqa: F401
from modules.students.models import Student  # noqa: F401


class Flag(TimestampedBase):
    __tablename__ = "pentrix_flags"

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pentrix_challenges.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    flag_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # hex-encoded SHA-256


class Submission(TimestampedBase):
    __tablename__ = "pentrix_submissions"
    __table_args__ = (UniqueConstraint("challenge_id", "student_id", name="uq_submission_challenge_student"),)

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pentrix_challenges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    solved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
