import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.communication.models import CommunicationChannel, CommunicationStatus


class SendCommunicationRequest(BaseModel):
    channel: CommunicationChannel
    recipient: str = Field(..., min_length=1, max_length=255)
    subject: str | None = Field(default=None, max_length=255)
    body: str = Field(..., min_length=1)


class CommunicationLogPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    channel: CommunicationChannel
    recipient: str
    subject: str | None
    body: str
    status: CommunicationStatus
    error_message: str | None
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    sent_by_user_id: uuid.UUID | None
    sent_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CommunicationLogListResponse(BaseModel):
    items: list[CommunicationLogPublic]
    total: int
