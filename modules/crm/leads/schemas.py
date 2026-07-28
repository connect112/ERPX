import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.crm.leads.models import LeadSource, LeadStatus


class LeadCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None
    phone: str | None = None
    branch_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    source: LeadSource = LeadSource.OTHER
    assigned_to_user_id: uuid.UUID | None = None
    notes: str | None = None


class LeadUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: str | None = None
    phone: str | None = None
    branch_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    source: LeadSource | None = None
    assigned_to_user_id: uuid.UUID | None = None
    notes: str | None = None


class LeadStatusChangeRequest(BaseModel):
    status: LeadStatus
    lost_reason: str | None = None


class LeadPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    campaign_id: uuid.UUID | None
    full_name: str
    email: str | None
    phone: str | None
    source: LeadSource
    status: LeadStatus
    assigned_to_user_id: uuid.UUID | None
    notes: str | None
    lost_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
