import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChapterCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    order_index: int = Field(..., ge=0)


class ChapterUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    order_index: int | None = Field(default=None, ge=0)


class ChapterPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: str | None
    order_index: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
