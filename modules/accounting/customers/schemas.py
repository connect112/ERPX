import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.accounting.customers.models import CustomerType


class CustomerCreateRequest(BaseModel):
    customer_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=255)
    customer_type: CustomerType = CustomerType.INDIVIDUAL
    student_id: uuid.UUID | None = None
    email: str | None = None
    phone: str | None = None
    gstin: str | None = Field(default=None, max_length=15)
    billing_address_line1: str | None = None
    billing_address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    credit_limit: float = Field(default=0, ge=0)
    notes: str | None = None


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = None
    phone: str | None = None
    gstin: str | None = None
    billing_address_line1: str | None = None
    billing_address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    credit_limit: float | None = Field(default=None, ge=0)
    notes: str | None = None
    is_active: bool | None = None


class CustomerPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    student_id: uuid.UUID | None
    customer_code: str
    name: str
    customer_type: CustomerType
    email: str | None
    phone: str | None
    gstin: str | None
    billing_address_line1: str | None
    billing_address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    credit_limit: float
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
