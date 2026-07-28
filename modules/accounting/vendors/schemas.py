import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VendorCreateRequest(BaseModel):
    vendor_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None
    phone: str | None = None
    gstin: str | None = Field(default=None, max_length=15)
    pan_number: str | None = Field(default=None, max_length=10)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    bank_account_number: str | None = Field(default=None, max_length=34)
    bank_ifsc_code: str | None = Field(default=None, max_length=11)
    bank_name: str | None = None
    notes: str | None = None


class VendorUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = None
    phone: str | None = None
    gstin: str | None = None
    pan_number: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    bank_account_number: str | None = None
    bank_ifsc_code: str | None = None
    bank_name: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class VendorPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    vendor_code: str
    name: str
    email: str | None
    phone: str | None
    gstin: str | None
    pan_number: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    bank_account_number: str | None
    bank_ifsc_code: str | None
    bank_name: str | None
    notes: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
