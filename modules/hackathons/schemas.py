import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator

from app.core.config import settings
from modules.hackathons.models import HackathonStatus
from modules.hackathons.slugs import clean_slug


class HackathonCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=2, max_length=255)
    theme: str | None = None
    description: str | None = None
    branch_id: uuid.UUID | None = None
    registration_deadline: date
    start_date: date
    end_date: date
    max_team_size: int = Field(default=4, ge=1, le=20)
    prize_pool: float | None = Field(default=None, ge=0)


class HackathonUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    theme: str | None = None
    description: str | None = None
    registration_deadline: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    max_team_size: int | None = Field(default=None, ge=1, le=20)
    prize_pool: float | None = Field(default=None, ge=0)
    leaderboard_visible: bool | None = None
    resubmission_enabled: bool | None = None
    max_resubmissions: int | None = Field(default=None, ge=0, le=50)
    leaderboard_share_enabled: bool | None = None
    leaderboard_slug: str | None = Field(default=None, min_length=3, max_length=60)
    leaderboard_show_members: bool | None = None
    leaderboard_show_graph: bool | None = None
    # Send null to clear a time. Both are moments in time (with a timezone, e.g. ending in Z).
    timer_starts_at: datetime | None = None
    timer_ends_at: datetime | None = None

    @field_validator("timer_starts_at", "timer_ends_at")
    @classmethod
    def _needs_a_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Give the time with its timezone.")
        return value

    @model_validator(mode="after")
    def _ends_after_it_starts(self):
        if self.timer_starts_at and self.timer_ends_at and self.timer_ends_at <= self.timer_starts_at:
            raise ValueError("The timer must end after it starts.")
        return self

    @field_validator("leaderboard_slug", mode="before")
    @classmethod
    def _clean_slug(cls, value):
        return clean_slug(value) if isinstance(value, str) else value

    @field_validator("leaderboard_slug")
    @classmethod
    def _slug_shape(cls, value):
        if value is not None and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", value):
            raise ValueError("Use only letters, numbers and single hyphens in the link name.")
        return value


class HackathonStatusChangeRequest(BaseModel):
    status: HackathonStatus


class HackathonPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    code: str
    title: str
    theme: str | None
    description: str | None
    registration_deadline: date
    start_date: date
    end_date: date
    max_team_size: int
    prize_pool: float | None
    status: HackathonStatus
    leaderboard_visible: bool = True
    resubmission_enabled: bool = True
    max_resubmissions: int = 2
    leaderboard_share_enabled: bool = False
    leaderboard_slug: str | None = None
    leaderboard_show_members: bool = False
    leaderboard_show_graph: bool = True
    timer_starts_at: datetime | None = None
    timer_ends_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def leaderboard_share_url(self) -> str | None:
        """Where the public live leaderboard lives (whether or not sharing is currently on)."""
        if not self.leaderboard_slug:
            return None
        return f"{settings.STUDENT_PORTAL_URL.rstrip('/')}/live/{self.leaderboard_slug}"


class HackathonListResponse(BaseModel):
    items: list[HackathonPublic]
    total: int


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


class TeamPublic(BaseModel):
    id: uuid.UUID
    hackathon_id: uuid.UUID
    created_by_student_id: uuid.UUID
    name: str
    created_at: datetime
    # Filled in by the list endpoints so students can see which teams are
    # full and staff can see who is in each team and how they are doing.
    member_count: int = 0
    member_names: list[str] = Field(default_factory=list)
    tasks_submitted: int = 0
    total_score: int = 0

    model_config = {"from_attributes": True}


class TeamOwnPublic(TeamPublic):
    """A team as its own members and staff see it: with the code teammates use to join."""

    join_code: str


class TeamJoinRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)


class TeamMemberPublic(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class ReportInfo(BaseModel):
    filename: str
    size_bytes: int
    uploaded_at: datetime


class TeamWithMembersPublic(BaseModel):
    team: TeamOwnPublic
    members: list[TeamMemberPublic]


def _trimmed(value):
    return value.strip() if isinstance(value, str) else value


class SubTaskInput(BaseModel):
    id: str | None = None  # an existing sub-task keeps its id when the task is edited
    title: str = Field(..., min_length=1, max_length=255)
    points: int = Field(..., ge=0, le=10000)

    _trim_title = field_validator("title", mode="before")(_trimmed)


class RubricRuleInput(BaseModel):
    id: str | None = None  # an existing rule keeps its id so scores already awarded stay attached
    criterion: str = Field(..., min_length=1, max_length=500)
    points: int = Field(..., ge=0, le=10000)

    _trim_criterion = field_validator("criterion", mode="before")(_trimmed)


class ProblemStatementInput(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    marks: int = Field(default=0, ge=0, le=10000)
    description: str | None = Field(default=None, max_length=20000)
    sub_tasks: list[SubTaskInput] = Field(default_factory=list, max_length=30)
    rubric: list[RubricRuleInput] = Field(default_factory=list, max_length=30)

    _trim_title = field_validator("title", mode="before")(_trimmed)

    @model_validator(mode="after")
    def _points_fit_in_the_marks(self):
        sub_total = sum(s.points for s in self.sub_tasks)
        rubric_total = sum(r.points for r in self.rubric)
        if (self.sub_tasks or self.rubric) and self.marks == 0:
            raise ValueError("Set the task's marks before adding sub-tasks or rubric rules.")
        if sub_total > self.marks:
            raise ValueError(f"The sub-tasks add up to {sub_total}, more than the task's {self.marks} marks.")
        if rubric_total > self.marks:
            raise ValueError(f"The rubric adds up to {rubric_total}, more than the task's {self.marks} marks.")
        return self


class SubTaskPublic(BaseModel):
    id: str
    title: str
    points: int


class RubricRulePublic(BaseModel):
    id: str
    criterion: str
    points: int


class ProblemStatementPublic(BaseModel):
    id: uuid.UUID
    hackathon_id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    marks: int = 0
    sub_tasks: list[SubTaskPublic] = Field(default_factory=list)
    rubric: list[RubricRulePublic] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    rank: int
    team_name: str
    score: int  # sum of the team's task scores
    tasks_scored: int
    members: list[str]


class LeaderboardBoard(BaseModel):
    hackathon_id: uuid.UUID
    hackathon_title: str
    published: bool
    # Total marks available across all tasks, so a chart can show progress to the maximum.
    max_total: int = 0
    # Whether to draw the bar graph (otherwise the teams are shown as a grid of cards).
    show_graph: bool = True
    entries: list[LeaderboardEntry] = Field(default_factory=list)


class AwardPublic(BaseModel):
    hackathon_id: uuid.UUID
    hackathon_title: str
    team_name: str
    code: str
    label: str
    detail: str


class TaskSubmissionInfo(BaseModel):
    id: uuid.UUID
    repo_url: str | None
    report: ReportInfo | None
    submitted_at: datetime
    score: int | None
    rubric_scores: dict[str, int] | None = None
    feedback: str | None
    resubmission_count: int = 0
    # False when staff have not scored the latest version yet (a score shown may be for an earlier one).
    reviewed: bool = False


class TaskPublic(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    marks: int = 0
    sub_tasks: list[SubTaskPublic] = Field(default_factory=list)
    rubric: list[RubricRulePublic] = Field(default_factory=list)
    submission: TaskSubmissionInfo | None = None
    # This team's place among the teams scored on this task (only while the leaderboard is shown).
    task_rank: int | None = None
    task_teams_scored: int = 0
    # Whether the team may change this submission now, and how many changes remain.
    can_resubmit: bool = False
    resubmissions_left: int = 0


class TasksResponse(BaseModel):
    """The tasks of a hackathon with the caller's team's submission for each."""

    team_id: uuid.UUID | None
    can_submit: bool
    max_total: int = 0
    leaderboard_visible: bool = True
    resubmission_enabled: bool = True
    max_resubmissions: int = 0
    # The team's overall place and total (only while the leaderboard is shown).
    team_rank: int | None = None
    team_total: int = 0
    teams_ranked: int = 0
    tasks: list[TaskPublic]


class TaskSubmissionAdmin(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    members: list[str]
    task_id: uuid.UUID
    task_title: str
    task_order: int
    task_marks: int = 0
    rubric: list[RubricRulePublic] = Field(default_factory=list)
    repo_url: str | None
    report_filename: str | None
    report_size_bytes: int | None
    submitted_at: datetime
    score: int | None
    rubric_scores: dict[str, int] | None = None
    reviewed: bool = False
    # Changed after first being submitted (and so possibly needs another look).
    resubmission_count: int = 0
    feedback: str | None


class TaskGradeRequest(BaseModel):
    """Marks for one submission: a mark per rubric rule for tasks that have a rubric,
    or a single score for tasks that don't."""

    score: int | None = Field(default=None, ge=0, le=1_000_000)
    rubric_scores: dict[str, int] | None = None
    feedback: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def _one_kind_of_marks(self):
        if self.score is None and self.rubric_scores is None:
            raise ValueError("Enter the marks.")
        if self.rubric_scores is not None and any(v < 0 for v in self.rubric_scores.values()):
            raise ValueError("Marks can't be negative.")
        return self


class ParticipantRow(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)


class ParticipantsRequest(BaseModel):
    participants: list[ParticipantRow] = Field(..., min_length=1, max_length=300)
    # Email a fresh set-password link to people who already have a login.
    resend_to_existing: bool = False


class ParticipantError(BaseModel):
    email: str
    reason: str


class ParticipantsResponse(BaseModel):
    created: int
    resent: int = 0
    already_have_login: int
    errors: list[ParticipantError]


class MessageResponse(BaseModel):
    message: str


# ---------------- organiser team and member controls ----------------


class MemberRef(BaseModel):
    """Someone to put in a team: an existing participant (by id), or a new person by
    name and email (a login is created for them if they don't have one)."""

    student_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)

    _trim_name = field_validator("name", mode="before")(_trimmed)

    @model_validator(mode="after")
    def _one_way_or_the_other(self):
        if self.student_id is None and not (self.name and self.email):
            raise ValueError("Pick a participant, or enter a name and an email.")
        return self


class TeamAdminCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    member: MemberRef  # the team's first member

    _trim_name = field_validator("name", mode="before")(_trimmed)


class TeamRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    _trim_name = field_validator("name", mode="before")(_trimmed)


class MemberMoveRequest(BaseModel):
    team_id: uuid.UUID


class MemberUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    # After an email change, send the new address a fresh set-password link.
    send_login_link: bool = True

    _trim_name = field_validator("full_name", mode="before")(_trimmed)


class RosterMemberPublic(BaseModel):
    student_id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    joined_at: datetime
    has_logged_in: bool
    is_creator: bool


class RosterTeamPublic(BaseModel):
    id: uuid.UUID
    name: str
    join_code: str
    created_at: datetime
    tasks_submitted: int = 0
    total_score: int = 0
    members: list[RosterMemberPublic]


class CandidatePublic(BaseModel):
    student_id: uuid.UUID
    full_name: str
    email: str | None
    student_code: str


# ---------------- everyone invited to a hackathon ----------------


class ParticipantPublic(BaseModel):
    student_id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    student_code: str
    invited_at: datetime | None
    has_logged_in: bool
    last_login_at: datetime | None
    team_id: uuid.UUID | None
    team_name: str | None
    is_creator: bool
    can_delete_account: bool


class ParticipantBulkRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=300)
    # False: just take them out of the hackathon. True: delete their ERPX accounts.
    delete_account: bool = False


class SkippedPerson(BaseModel):
    student_id: uuid.UUID
    name: str
    reason: str


class ParticipantBulkResult(BaseModel):
    done: int
    skipped: list[SkippedPerson] = Field(default_factory=list)


class LoginLinksRequest(BaseModel):
    # None = everyone who hasn't signed in yet.
    student_ids: list[uuid.UUID] | None = Field(default=None, max_length=300)


class PublicLeaderboardEntry(BaseModel):
    rank: int
    team_name: str
    score: int
    tasks_scored: int
    members: list[str] = Field(default_factory=list)  # empty unless the organiser chose to show names


class PublicLeaderboard(BaseModel):
    title: str
    theme: str | None
    status: HackathonStatus
    max_total: int = 0
    show_members: bool = False
    show_graph: bool = True
    updated_at: datetime
    # The event's countdown, and the server's clock so a screen with the wrong time still counts down right.
    timer_starts_at: datetime | None = None
    timer_ends_at: datetime | None = None
    server_time: datetime
    entries: list[PublicLeaderboardEntry]
