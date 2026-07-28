import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.events.models import EventType


class EventCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    event_type: EventType = EventType.OTHER
    start_at: datetime
    end_at: datetime | None = None
    location: str | None = None
    is_all_day: bool = False


class EventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    event_type: EventType | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = None
    is_all_day: bool | None = None


class EventPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    title: str
    description: str | None
    event_type: EventType
    start_at: datetime
    end_at: datetime | None
    location: str | None
    is_all_day: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
