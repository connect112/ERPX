import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TDSSectionCreateRequest(BaseModel):
    section_code: str = Field(..., min_length=2, max_length=10)
    description: str = Field(..., min_length=2, max_length=255)
    rate_percent: float = Field(..., ge=0, le=100)
    threshold_amount: float = Field(default=0, ge=0)


class TDSSectionUpdateRequest(BaseModel):
    description: str | None = None
    rate_percent: float | None = Field(default=None, ge=0, le=100)
    threshold_amount: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class TDSSectionPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    section_code: str
    description: str
    rate_percent: float
    threshold_amount: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TDSDeductionPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    vendor_id: uuid.UUID
    tds_section_id: uuid.UUID
    payment_id: uuid.UUID | None
    gross_amount: float
    tds_amount: float
    net_amount: float
    financial_year: str
    certificate_number: str | None
    deduction_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
