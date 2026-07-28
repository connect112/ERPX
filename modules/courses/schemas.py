import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.courses.models import CourseLevel


class CourseCreateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    title: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    short_description: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    level: CourseLevel = CourseLevel.BEGINNER
    duration_hours: int | None = Field(default=None, ge=0)
    price: float = Field(default=0, ge=0)


class CourseUpdateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=255)
    short_description: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    level: CourseLevel | None = None
    duration_hours: int | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    is_published: bool | None = None


class CoursePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    category_id: uuid.UUID | None
    title: str
    slug: str
    short_description: str | None
    description: str | None
    thumbnail_url: str | None
    level: CourseLevel
    duration_hours: int | None
    price: float
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
