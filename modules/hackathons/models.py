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
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
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
    # Whether participants can see the team leaderboard. On by default so it
    # updates live as tasks are scored; the organiser can hide it while judging.
    leaderboard_visible: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    # Whether a team may change a task submission after it has been made, and how
    # many times (the first submission does not count).
    resubmission_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    max_resubmissions: Mapped[int] = mapped_column(Integer, default=2, server_default="2", nullable=False)


class ProblemStatement(TimestampedBase):
    """A challenge teams can choose to work on in a hackathon."""

    __tablename__ = "hackathon_problem_statements"

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Optional: the admin form shows it behind a toggle.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # Maximum marks for the task. 0 = no maximum set (older tasks), scored freely.
    marks: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # [{"id", "title", "points"}]: the parts of the task and what each is worth.
    sub_tasks: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    # [{"id", "criterion", "points"}]: what staff mark a submission on; points sum to at most `marks`.
    rubric: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)


class Team(TimestampedBase):
    __tablename__ = "hackathon_teams"
    __table_args__ = (
        UniqueConstraint("hackathon_id", "name", name="uq_hackathon_team_name"),
        UniqueConstraint("hackathon_id", "join_code", name="uq_hackathon_team_join_code"),
    )

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # What a teammate types to join this team; shown only to staff and the team's own members.
    join_code: Mapped[str] = mapped_column(String(12), nullable=False)
    problem_statement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hackathon_problem_statements.id", ondelete="SET NULL"), nullable=True
    )


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


class TeamReport(TimestampedBase):
    """The team's written report (PDF/Word/PowerPoint/zip), one per team.

    Kept in the database next to the team rather than in object storage: a
    hackathon has a few dozen reports of a few MB each, the API streams them
    behind the same auth as everything else, and there is no presigned-URL
    host to get wrong in production.
    """

    __tablename__ = "hackathon_team_reports"
    __table_args__ = (UniqueConstraint("team_id", name="uq_hackathon_team_report_team"),)

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_by_student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )


class TaskSubmission(TimestampedBase):
    """A team's work on one task (problem statement): a report file and/or a
    repository / registry URL, scored by staff. One row per team per task; the
    leaderboard ranks teams by the sum of their task scores.

    The older whole-hackathon `Submission` and `TeamReport` tables are no
    longer written to (their data was copied here when this table was added).
    """

    __tablename__ = "hackathon_task_submissions"
    __table_args__ = (UniqueConstraint("team_id", "problem_statement_id", name="uq_hackathon_task_submission"),)

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathon_teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    problem_statement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathon_problem_statements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    report_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    submitted_by_student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # {rubric rule id: marks awarded}; `score` is their sum (or a free score for tasks with no rubric).
    rubric_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    # How many times the team has changed this submission after first making it.
    resubmission_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # When staff last scored it. A submission is reviewed only while this is later than
    # `submitted_at`, so a resubmission shows as unreviewed again (its old score stays
    # on the leaderboard until it is re-scored).
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HackathonParticipant(TimestampedBase):
    """Someone invited to a hackathon (bulk-added by an organiser, or added to a team by one).
    `created_at` is when they were invited. People who are in one of its teams count as
    participants too, even without a row here."""

    __tablename__ = "hackathon_participants"
    __table_args__ = (UniqueConstraint("hackathon_id", "student_id", name="uq_hackathon_participant"),)

    hackathon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
