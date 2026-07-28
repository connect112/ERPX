import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.internships.models import InternshipApplicationStatus, InternshipPostingStatus, InternshipStatus


class InternshipPostingCreateRequest(BaseModel):
    company_id: uuid.UUID
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    duration_months: int | None = Field(default=None, ge=1, le=36)
    stipend: float | None = Field(default=None, ge=0)
    location: str | None = None
    required_skills: str | None = None
    application_deadline: date | None = None


class InternshipPostingUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    duration_months: int | None = Field(default=None, ge=1, le=36)
    stipend: float | None = Field(default=None, ge=0)
    location: str | None = None
    required_skills: str | None = None
    application_deadline: date | None = None


class InternshipPostingStatusChangeRequest(BaseModel):
    status: InternshipPostingStatus


class InternshipPostingPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: uuid.UUID
    title: str
    description: str | None
    duration_months: int | None
    stipend: float | None
    location: str | None
    required_skills: str | None
    application_deadline: date | None
    status: InternshipPostingStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class InternshipPostingListResponse(BaseModel):
    items: list[InternshipPostingPublic]
    total: int


class InternshipApplicationCreateRequest(BaseModel):
    cover_letter: str | None = None


class InternshipApplicationStatusChangeRequest(BaseModel):
    status: InternshipApplicationStatus
    notes: str | None = None


class InternshipApplicationPublic(BaseModel):
    id: uuid.UUID
    internship_posting_id: uuid.UUID
    student_id: uuid.UUID
    applied_at: datetime
    cover_letter: str | None
    status: InternshipApplicationStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InternshipUpdateRequest(BaseModel):
    mentor_employee_id: uuid.UUID | None = None
    end_date: date | None = None
    stipend: float | None = Field(default=None, ge=0)
    feedback: str | None = None


class InternshipStatusChangeRequest(BaseModel):
    status: InternshipStatus


class InternshipPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    application_id: uuid.UUID
    internship_posting_id: uuid.UUID
    student_id: uuid.UUID
    mentor_employee_id: uuid.UUID | None
    start_date: date
    end_date: date | None
    stipend: float | None
    status: InternshipStatus
    feedback: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InternshipListResponse(BaseModel):
    items: list[InternshipPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
