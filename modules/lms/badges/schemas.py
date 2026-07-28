import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BadgeCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: str | None = None
    icon_url: str | None = None


class BadgePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    icon_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AwardBadgeRequest(BaseModel):
    student_id: uuid.UUID
    badge_id: uuid.UUID


class StudentBadgePublic(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    badge_id: uuid.UUID
    awarded_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
