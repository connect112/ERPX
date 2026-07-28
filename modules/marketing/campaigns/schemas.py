import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.marketing.campaigns.models import CampaignChannel, CampaignStatus


class CampaignCreateRequest(BaseModel):
    campaign_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=255)
    branch_id: uuid.UUID | None = None
    channel: CampaignChannel
    start_date: date
    end_date: date | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    target_audience: str | None = None
    goal: str | None = None
    notes: str | None = None


class CampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    end_date: date | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    actual_spend: float | None = Field(default=None, ge=0)
    target_audience: str | None = None
    goal: str | None = None
    notes: str | None = None


class CampaignStatusChangeRequest(BaseModel):
    status: CampaignStatus


class CampaignPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    campaign_code: str
    name: str
    channel: CampaignChannel
    status: CampaignStatus
    start_date: date
    end_date: date | None
    budget_amount: float | None
    actual_spend: float
    target_audience: str | None
    goal: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
