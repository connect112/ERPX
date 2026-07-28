import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.organizations.models import SubscriptionPlan


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=150, pattern=r"^[a-z0-9-]+$")
    legal_name: str | None = None
    industry: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    subscription_plan: SubscriptionPlan = SubscriptionPlan.TRIAL


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    legal_name: str | None = None
    industry: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    logo_url: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    subscription_plan: SubscriptionPlan | None = None
    is_active: bool | None = None


class OrganizationPublic(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    legal_name: str | None
    industry: str | None
    email: str | None
    phone: str | None
    website: str | None
    logo_url: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    subscription_plan: SubscriptionPlan
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
