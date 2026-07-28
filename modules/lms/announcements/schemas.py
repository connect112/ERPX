import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AnnouncementCreateRequest(BaseModel):
    course_id: uuid.UUID | None = None
    title: str = Field(..., min_length=2, max_length=255)
    body: str = Field(..., min_length=1)


class AnnouncementUpdateRequest(BaseModel):
    title: str | None = None
    body: str | None = None


class AnnouncementPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    course_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    title: str
    body: str
    published_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
