import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.corporate.quotations.models import QuotationStatus


class QuotationLineRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    quantity: float = Field(default=1, gt=0)
    unit_price: float = Field(..., ge=0)
    gst_rate_id: uuid.UUID | None = None


class QuotationCreateRequest(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    quotation_number: str = Field(..., min_length=1, max_length=50)
    quotation_date: date
    valid_until: date
    notes: str | None = None
    lines: list[QuotationLineRequest] = Field(..., min_length=1)


class QuotationUpdateRequest(BaseModel):
    valid_until: date | None = None
    notes: str | None = None
    lines: list[QuotationLineRequest] | None = None


class QuotationLinePublic(BaseModel):
    id: uuid.UUID
    gst_rate_id: uuid.UUID | None
    description: str
    quantity: float
    unit_price: float
    line_subtotal: float
    tax_amount: float
    line_total: float

    model_config = {"from_attributes": True}


class QuotationPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID | None
    quotation_number: str
    quotation_date: date
    valid_until: date
    status: QuotationStatus
    subtotal_amount: float
    tax_amount: float
    total_amount: float
    notes: str | None
    rejection_reason: str | None
    created_at: datetime
    lines: list[QuotationLinePublic] = []

    model_config = {"from_attributes": True}


class QuotationRejectRequest(BaseModel):
    rejection_reason: str | None = None


class MessageResponse(BaseModel):
    message: str
