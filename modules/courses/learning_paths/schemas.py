import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LearningPathCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: str | None = None


class LearningPathUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None


class LearningPathCoursePublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    order_index: int

    model_config = {"from_attributes": True}


class AddCourseToPathRequest(BaseModel):
    course_id: uuid.UUID
    order_index: int = Field(..., ge=0)


class LearningPathPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    slug: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LearningPathWithCourses(LearningPathPublic):
    courses: list[LearningPathCoursePublic] = []


class MessageResponse(BaseModel):
    message: str
