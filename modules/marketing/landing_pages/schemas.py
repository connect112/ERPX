import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.marketing.landing_pages.models import LandingPageStatus


class LandingPageCreateRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    title: str = Field(..., min_length=2, max_length=255)
    campaign_id: uuid.UUID | None = None
    meta_description: str | None = Field(default=None, max_length=500)
    content: str = Field(..., min_length=1)


class LandingPageUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    campaign_id: uuid.UUID | None = None
    meta_description: str | None = None
    content: str | None = None


class LandingPagePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    campaign_id: uuid.UUID | None
    slug: str
    title: str
    meta_description: str | None
    content: str
    status: LandingPageStatus
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LandingPageViewCreateRequest(BaseModel):
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    referrer_url: str | None = Field(default=None, max_length=512)


class LandingPageViewPublic(BaseModel):
    id: uuid.UUID
    landing_page_id: uuid.UUID
    converted_to_lead_id: uuid.UUID | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    referrer_url: str | None
    viewed_at: datetime

    model_config = {"from_attributes": True}


class LandingPageStatsResponse(BaseModel):
    landing_page_id: uuid.UUID
    total_views: int
    total_conversions: int
    conversion_rate_percent: float


class MessageResponse(BaseModel):
    message: str
