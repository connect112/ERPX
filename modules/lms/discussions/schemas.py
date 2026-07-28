import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ThreadCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    body: str = Field(..., min_length=1)


class ThreadPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    title: str
    body: str
    is_locked: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReplyCreateRequest(BaseModel):
    body: str = Field(..., min_length=1)


class ReplyPublic(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
