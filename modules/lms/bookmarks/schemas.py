import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookmarkPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lesson_id: uuid.UUID
    lesson_title: str
    course_id: uuid.UUID
    course_title: str
    created_at: datetime


class MessageResponse(BaseModel):
    message: str
