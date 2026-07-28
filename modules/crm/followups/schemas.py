import uuid
from datetime import datetime

from pydantic import BaseModel

from modules.crm.followups.models import FollowUpStatus, FollowUpType


class FollowUpCreateRequest(BaseModel):
    follow_up_type: FollowUpType = FollowUpType.CALL
    scheduled_at: datetime
    notes: str | None = None


class FollowUpCompleteRequest(BaseModel):
    outcome: str
    notes: str | None = None


class FollowUpUpdateRequest(BaseModel):
    follow_up_type: FollowUpType | None = None
    scheduled_at: datetime | None = None
    status: FollowUpStatus | None = None
    notes: str | None = None


class FollowUpPublic(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    follow_up_type: FollowUpType
    status: FollowUpStatus
    scheduled_at: datetime
    completed_at: datetime | None
    outcome: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
