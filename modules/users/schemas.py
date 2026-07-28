import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.users.models import Gender


class UserProfileCreateRequest(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    employee_code: str | None = None
    designation: str | None = None
    department: str | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    date_of_joining: date | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None


class UserProfileUpdateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    employee_code: str | None = None
    designation: str | None = None
    department: str | None = None
    avatar_url: str | None = None
    gender: Gender | None = None
    date_of_birth: date | None = None
    date_of_joining: date | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None


class UserProfilePublic(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    employee_code: str | None
    designation: str | None
    department: str | None
    avatar_url: str | None
    gender: Gender | None
    date_of_birth: date | None
    date_of_joining: date | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserWithProfilePublic(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    status: str
    is_email_verified: bool
    profile: UserProfilePublic | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
