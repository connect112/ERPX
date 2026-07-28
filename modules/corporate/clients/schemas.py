import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.corporate.clients.models import ClientStatus


class ClientCreateRequest(BaseModel):
    client_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=255)
    branch_id: uuid.UUID | None = None
    accounting_customer_id: uuid.UUID | None = None
    account_manager_user_id: uuid.UUID | None = None
    industry: str | None = None
    website: str | None = None
    gstin: str | None = Field(default=None, max_length=15)
    contact_person_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    notes: str | None = None


class ClientUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    accounting_customer_id: uuid.UUID | None = None
    account_manager_user_id: uuid.UUID | None = None
    industry: str | None = None
    website: str | None = None
    gstin: str | None = None
    contact_person_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    notes: str | None = None


class ClientStatusChangeRequest(BaseModel):
    status: ClientStatus


class ClientPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    accounting_customer_id: uuid.UUID | None
    account_manager_user_id: uuid.UUID | None
    client_code: str
    name: str
    industry: str | None
    website: str | None
    gstin: str | None
    contact_person_name: str | None
    contact_email: str | None
    contact_phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    status: ClientStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
