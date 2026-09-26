import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.placements.models import (
    AggregationRunStatus,
    ApplicationStatus,
    JobPostingStatus,
    JobType,
)


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
    # Aggregation-pipeline attribution fields. "manual" for every
    # staff-created posting (the pre-existing default) — see
    # modules/placements/aggregation_service.py.
    source: str
    source_url: str | None
    last_seen_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobPostingListResponse(BaseModel):
    items: list[JobPostingPublic]
    total: int


class AggregationRunSourcePublic(BaseModel):
    source: str
    status: str
    postings_fetched: int
    request_count: int
    error_message: str | None

    model_config = {"from_attributes": True}


class AggregationRunPublic(BaseModel):
    id: uuid.UUID
    triggered_by: str
    status: AggregationRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    postings_created: int
    postings_updated: int
    postings_closed: int
    matches_created: int
    error_message: str | None
    created_at: datetime
    sources: list[AggregationRunSourcePublic] = []

    model_config = {"from_attributes": True}


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
