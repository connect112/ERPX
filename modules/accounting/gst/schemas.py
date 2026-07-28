import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class GSTRateCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    rate_percent: float = Field(..., ge=0, le=100)
    hsn_sac_code: str | None = Field(default=None, max_length=20)


class GSTRateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    rate_percent: float | None = Field(default=None, ge=0, le=100)
    hsn_sac_code: str | None = None
    is_active: bool | None = None


class GSTRatePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    rate_percent: float
    hsn_sac_code: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TaxComputationRequest(BaseModel):
    taxable_amount: float = Field(..., ge=0)
    gst_rate_id: uuid.UUID
    is_interstate: bool = False


class TaxComputationResponse(BaseModel):
    taxable_amount: float
    rate_percent: float
    is_interstate: bool
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    total_tax: float
    total_amount: float


class GSTReturnSummaryResponse(BaseModel):
    period_from: date
    period_to: date
    output_taxable_value: float
    output_tax_collected: float
    input_taxable_value: float
    input_tax_credit: float
    net_tax_payable: float


class MessageResponse(BaseModel):
    message: str
