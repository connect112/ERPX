import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.alumni.models import EventMode, EventStatus, ReferralStatus, RegistrationStatus


class AlumniProfileCreateRequest(BaseModel):
    graduation_year: int | None = Field(default=None, ge=1990, le=2100)
    current_company: str | None = None
    current_designation: str | None = None
    current_location: str | None = None
    linkedin_url: str | None = None
    bio: str | None = None


class AlumniProfileUpdateRequest(BaseModel):
    graduation_year: int | None = Field(default=None, ge=1990, le=2100)
    current_company: str | None = None
    current_designation: str | None = None
    current_location: str | None = None
    linkedin_url: str | None = None
    bio: str | None = None


class AlumniProfileVerifyRequest(BaseModel):
    is_verified: bool


class AlumniProfilePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    student_id: uuid.UUID
    graduation_year: int | None
    current_company: str | None
    current_designation: str | None
    current_location: str | None
    linkedin_url: str | None
    bio: str | None
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlumniProfileListResponse(BaseModel):
    items: list[AlumniProfilePublic]
    total: int


class AlumniEventCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    mode: EventMode = EventMode.VIRTUAL
    venue: str | None = None
    meeting_link: str | None = None
    event_date: date
    registration_deadline: date | None = None


class AlumniEventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    mode: EventMode | None = None
    venue: str | None = None
    meeting_link: str | None = None
    event_date: date | None = None
    registration_deadline: date | None = None


class AlumniEventStatusChangeRequest(BaseModel):
    status: EventStatus


class AlumniEventPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    description: str | None
    mode: EventMode
    venue: str | None
    meeting_link: str | None
    event_date: date
    registration_deadline: date | None
    status: EventStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AlumniEventListResponse(BaseModel):
    items: list[AlumniEventPublic]
    total: int


class EventRegistrationAttendanceRequest(BaseModel):
    status: RegistrationStatus


class EventRegistrationPublic(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    alumni_id: uuid.UUID
    registered_at: datetime
    status: RegistrationStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class JobReferralCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    contact_email: str | None = None
    referral_link: str | None = None


class JobReferralUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    company: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    contact_email: str | None = None
    referral_link: str | None = None
    status: ReferralStatus | None = None


class JobReferralPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    alumni_id: uuid.UUID
    title: str
    company: str
    description: str | None
    contact_email: str | None
    referral_link: str | None
    status: ReferralStatus
    posted_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class JobReferralListResponse(BaseModel):
    items: list[JobReferralPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
