import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.crm.enquiries.models import EnquiryStatus


class EnquiryCreateRequest(BaseModel):
    course_interest: str = Field(..., min_length=2, max_length=255)
    budget: float | None = None
    preferred_batch_timing: str | None = None
    notes: str | None = None


class EnquiryUpdateRequest(BaseModel):
    course_interest: str | None = None
    budget: float | None = None
    preferred_batch_timing: str | None = None
    status: EnquiryStatus | None = None
    notes: str | None = None


class EnquiryPublic(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    course_interest: str
    budget: float | None
    preferred_batch_timing: str | None
    status: EnquiryStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
