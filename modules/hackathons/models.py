"""
Hackathons module — ORM models.

Team-based project competitions, distinct from Pentrix (individual
CTF flag-capturing). A `Team` belongs to one `Hackathon`;
`TeamMember` rows are the roster, with `Team.created_by_student_id`
identifying the team leader rather than a separate role column — a
hackathon team is small (capped by `Hackathon.max_team_size`) and
"who created it" is the only leadership distinction that matters here.
`Submission` is one row per team per hackathon (a team resubmits by
updating the same row up to the deadline, not by creating new rows).
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class HackathonStatus(str, enum.Enum):
    DRAFT = "draft"
    REGISTRATION_OPEN = "registration_open"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Hackathon(TimestampedBase):
    __tablename__ = "hackathons"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_hackathon_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    theme: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_deadline: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    max_team_size: Mapped[int] = mapped_column(Integer, default=4, server_default="4", nullable=False)
    prize_pool: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[HackathonStatus] = mapped_column(
        SAEnum(HackathonStatus, name="hackathon_status", values_callable=_values),
        default=HackathonStatus.DRAFT,
        server_default=HackathonStatus.DRAFT.value,
        nullable=False,
        index=True,
    )


class Team(TimestampedBase):
    __tablename__ = "hackathon_teams"
    __table_args__ = (UniqueConstraint("hackathon_id", "name", name="uq_hackathon_team_name"),)

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class TeamMember(TimestampedBase):
    __tablename__ = "hackathon_team_members"
    __table_args__ = (UniqueConstraint("team_id", "student_id", name="uq_team_member_student"),)

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Submission(TimestampedBase):
    __tablename__ = "hackathon_submissions"
    __table_args__ = (UniqueConstraint("team_id", name="uq_hackathon_submission_team"),)

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
