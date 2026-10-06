import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from modules.hackathons.models import HackathonStatus


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
    created_at: datetime

    model_config = {"from_attributes": True}


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
    team: TeamPublic
    members: list[TeamMemberPublic]


class ProblemStatementInput(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=1, max_length=20000)


class ProblemStatementPublic(BaseModel):
    id: uuid.UUID
    hackathon_id: uuid.UUID
    title: str
    description: str
    order_index: int

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
    feedback: str | None


class TaskPublic(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    order_index: int
    submission: TaskSubmissionInfo | None = None


class TasksResponse(BaseModel):
    """The tasks of a hackathon with the caller's team's submission for each."""

    team_id: uuid.UUID | None
    can_submit: bool
    tasks: list[TaskPublic]


class TaskSubmissionAdmin(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    team_name: str
    members: list[str]
    task_id: uuid.UUID
    task_title: str
    task_order: int
    repo_url: str | None
    report_filename: str | None
    report_size_bytes: int | None
    submitted_at: datetime
    score: int | None
    feedback: str | None


class TaskGradeRequest(BaseModel):
    score: int = Field(..., ge=0, le=1_000_000)
    feedback: str | None = Field(default=None, max_length=5000)


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
