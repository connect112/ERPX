import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, Field

from modules.workshops.models import RegistrationStatus, WorkshopMode, WorkshopStatus


class WorkshopCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    branch_id: uuid.UUID | None = None
    trainer_id: uuid.UUID | None = None
    mode: WorkshopMode = WorkshopMode.PHYSICAL
    venue: str | None = None
    meeting_link: str | None = None
    workshop_date: date
    start_time: time
    end_time: time
    capacity: int | None = Field(default=None, ge=1)
    fee: float = Field(default=0, ge=0)


class WorkshopUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    branch_id: uuid.UUID | None = None
    trainer_id: uuid.UUID | None = None
    mode: WorkshopMode | None = None
    venue: str | None = None
    meeting_link: str | None = None
    workshop_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    capacity: int | None = Field(default=None, ge=1)
    fee: float | None = Field(default=None, ge=0)


class WorkshopStatusChangeRequest(BaseModel):
    status: WorkshopStatus


class WorkshopPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    trainer_id: uuid.UUID | None
    code: str
    title: str
    description: str | None
    mode: WorkshopMode
    venue: str | None
    meeting_link: str | None
    workshop_date: date
    start_time: time
    end_time: time
    capacity: int | None
    fee: float
    status: WorkshopStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkshopListResponse(BaseModel):
    items: list[WorkshopPublic]
    total: int


class WorkshopRegistrationCreateRequest(BaseModel):
    student_id: uuid.UUID | None = None
    contact_name: str = Field(..., min_length=2, max_length=255)
    contact_email: str | None = None
    contact_phone: str | None = None


class WorkshopRegistrationPublic(BaseModel):
    id: uuid.UUID
    workshop_id: uuid.UUID
    student_id: uuid.UUID | None
    contact_name: str
    contact_email: str | None
    contact_phone: str | None
    registered_at: datetime
    status: RegistrationStatus
    is_paid: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MarkAttendanceRequest(BaseModel):
    attended: bool


class MessageResponse(BaseModel):
    message: str
