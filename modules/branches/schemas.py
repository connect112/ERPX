import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BranchCreateRequest(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    is_head_office: bool = False


class BranchUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    is_head_office: bool | None = None
    is_active: bool | None = None


class BranchPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    phone: str | None
    email: str | None
    is_head_office: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
