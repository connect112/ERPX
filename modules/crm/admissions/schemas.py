import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.crm.admissions.models import AdmissionStatus


class AdmissionCreateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    course_name: str = Field(..., min_length=2, max_length=255)
    batch_name: str | None = None
    fee_amount: float = Field(..., ge=0)
    discount_amount: float = Field(default=0, ge=0)
    admission_date: date


class AdmissionUpdateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    course_name: str | None = None
    batch_name: str | None = None
    fee_amount: float | None = Field(default=None, ge=0)
    discount_amount: float | None = Field(default=None, ge=0)
    admission_date: date | None = None
    status: AdmissionStatus | None = None


class AdmissionPublic(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    course_name: str
    batch_name: str | None
    fee_amount: float
    discount_amount: float
    admission_date: date
    status: AdmissionStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
