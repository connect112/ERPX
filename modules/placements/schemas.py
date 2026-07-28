import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.placements.models import ApplicationStatus, JobPostingStatus, JobType


class CompanyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    industry: str | None = None
    website: str | None = None
    contact_person_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    industry: str | None = None
    website: str | None = None
    contact_person_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class CompanyPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    industry: str | None
    website: str | None
    contact_person_name: str | None
    contact_email: str | None
    contact_phone: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    items: list[CompanyPublic]
    total: int


class JobPostingCreateRequest(BaseModel):
    company_id: uuid.UUID
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    job_type: JobType = JobType.FULL_TIME
    location: str | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    required_skills: str | None = None
    application_deadline: date | None = None


class JobPostingUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    job_type: JobType | None = None
    location: str | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    required_skills: str | None = None
    application_deadline: date | None = None


class JobPostingStatusChangeRequest(BaseModel):
    status: JobPostingStatus


class JobPostingPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    company_id: uuid.UUID
    title: str
    description: str | None
    job_type: JobType
    location: str | None
    salary_min: float | None
    salary_max: float | None
    required_skills: str | None
    application_deadline: date | None
    status: JobPostingStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class JobPostingListResponse(BaseModel):
    items: list[JobPostingPublic]
    total: int


class ApplicationCreateRequest(BaseModel):
    cover_letter: str | None = None


class ApplicationStatusChangeRequest(BaseModel):
    status: ApplicationStatus
    notes: str | None = None


class ApplicationPublic(BaseModel):
    id: uuid.UUID
    job_posting_id: uuid.UUID
    student_id: uuid.UUID
    applied_at: datetime
    cover_letter: str | None
    status: ApplicationStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
