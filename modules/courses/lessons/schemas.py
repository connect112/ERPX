import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.courses.lessons.models import LessonContentType


class LessonCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    content_type: LessonContentType = LessonContentType.VIDEO
    video_url: str | None = None
    content_text: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    order_index: int = Field(..., ge=0)
    is_preview: bool = False


class LessonUpdateRequest(BaseModel):
    title: str | None = None
    content_type: LessonContentType | None = None
    video_url: str | None = None
    content_text: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    order_index: int | None = Field(default=None, ge=0)
    is_preview: bool | None = None


class LessonPublic(BaseModel):
    id: uuid.UUID
    chapter_id: uuid.UUID
    title: str
    content_type: LessonContentType
    video_url: str | None
    content_text: str | None
    duration_minutes: int | None
    order_index: int
    is_preview: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
