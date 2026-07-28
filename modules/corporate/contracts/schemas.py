import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.corporate.contracts.models import ContractStatus, ContractType


class ContractCreateRequest(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    quotation_id: uuid.UUID | None = None
    contract_number: str = Field(..., min_length=1, max_length=50)
    contract_type: ContractType
    start_date: date
    end_date: date | None = None
    contract_value: float = Field(..., ge=0)
    document_url: str | None = Field(default=None, max_length=512)
    notes: str | None = None


class ContractUpdateRequest(BaseModel):
    end_date: date | None = None
    contract_value: float | None = Field(default=None, ge=0)
    document_url: str | None = None
    notes: str | None = None


class ContractActivateRequest(BaseModel):
    signed_date: date


class ContractRenewRequest(BaseModel):
    new_end_date: date
    new_contract_value: float | None = Field(default=None, ge=0)


class ContractPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID | None
    quotation_id: uuid.UUID | None
    contract_number: str
    contract_type: ContractType
    start_date: date
    end_date: date | None
    contract_value: float
    status: ContractStatus
    signed_date: date | None
    document_url: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
