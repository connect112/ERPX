import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

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

    model_config = {"from_attributes": True}


class TeamMemberPublic(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class TeamWithMembersPublic(BaseModel):
    team: TeamPublic
    members: list[TeamMemberPublic]


class SubmissionCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    repo_url: str | None = None
    demo_url: str | None = None


class SubmissionGradeRequest(BaseModel):
    score: int = Field(..., ge=0)
    feedback: str | None = None


class SubmissionPublic(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    title: str
    description: str | None
    repo_url: str | None
    demo_url: str | None
    submitted_at: datetime
    score: int | None
    feedback: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
