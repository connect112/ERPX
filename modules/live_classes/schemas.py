import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.live_classes.models import LiveClassStatus


class LiveClassCreateRequest(BaseModel):
    batch_id: uuid.UUID
    trainer_id: uuid.UUID | None = None
    title: str = Field(..., min_length=2, max_length=255)
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=480)
    meeting_link: str = Field(..., min_length=1, max_length=512)


class LiveClassUpdateRequest(BaseModel):
    trainer_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=255)
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    meeting_link: str | None = Field(default=None, min_length=1, max_length=512)


class LiveClassStatusChangeRequest(BaseModel):
    status: LiveClassStatus
    recording_url: str | None = None


class LiveClassPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    batch_id: uuid.UUID
    trainer_id: uuid.UUID | None
    title: str
    scheduled_at: datetime
    duration_minutes: int
    meeting_link: str
    recording_url: str | None
    status: LiveClassStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class LiveClassListResponse(BaseModel):
    items: list[LiveClassPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
