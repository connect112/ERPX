import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.corporate.amc.models import AMCStatus, AMCVisitStatus, BillingFrequency


class AMCContractCreateRequest(BaseModel):
    client_id: uuid.UUID
    contract_id: uuid.UUID | None = None
    amc_number: str = Field(..., min_length=1, max_length=50)
    coverage_description: str = Field(..., min_length=2)
    start_date: date
    end_date: date
    renewal_reminder_days: int = Field(default=30, ge=1)
    amount: float = Field(..., ge=0)
    billing_frequency: BillingFrequency


class AMCContractUpdateRequest(BaseModel):
    coverage_description: str | None = None
    end_date: date | None = None
    renewal_reminder_days: int | None = Field(default=None, ge=1)
    amount: float | None = Field(default=None, ge=0)
    billing_frequency: BillingFrequency | None = None
    status: AMCStatus | None = None


class AMCContractPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    client_id: uuid.UUID
    contract_id: uuid.UUID | None
    amc_number: str
    coverage_description: str
    start_date: date
    end_date: date
    renewal_reminder_days: int
    amount: float
    billing_frequency: BillingFrequency
    status: AMCStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AMCVisitCreateRequest(BaseModel):
    visit_date: date
    purpose: str = Field(..., min_length=2, max_length=500)
    engineer_employee_id: uuid.UUID | None = None


class AMCVisitCompleteRequest(BaseModel):
    findings: str = Field(..., min_length=2)


class AMCVisitPublic(BaseModel):
    id: uuid.UUID
    amc_contract_id: uuid.UUID
    engineer_employee_id: uuid.UUID | None
    visit_date: date
    purpose: str
    findings: str | None
    status: AMCVisitStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
