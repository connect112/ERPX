import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ThreadCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    body: str = Field(..., min_length=1)
    # Set to start a thread that is private to ONE internship: only that internship's students and staff can see it. Omit for a course-wide thread.
    internship_id: uuid.UUID | None = None


class ThreadPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    internship_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None
    author_name: str | None = None
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
    author_name: str | None = None
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LockRequest(BaseModel):
    is_locked: bool


class MessageResponse(BaseModel):
    message: str
