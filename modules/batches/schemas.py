import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.batches.models import BatchStatus


class BatchCreateRequest(BaseModel):
    course_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    trainer_id: uuid.UUID | None = None
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    capacity: int | None = Field(default=None, ge=1)
    start_date: date
    end_date: date | None = None


class BatchUpdateRequest(BaseModel):
    branch_id: uuid.UUID | None = None
    trainer_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=255)
    status: BatchStatus | None = None
    capacity: int | None = Field(default=None, ge=1)
    start_date: date | None = None
    end_date: date | None = None


class BatchPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    course_id: uuid.UUID
    trainer_id: uuid.UUID | None
    name: str
    code: str
    status: BatchStatus
    capacity: int | None
    start_date: date
    end_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchWithCoursePublic(BatchPublic):
    course_title: str


class MyBatchEnrollmentPublic(BaseModel):
    """A student's own batch membership — what `GET /batches/student/me` returns."""

    id: uuid.UUID
    batch: BatchWithCoursePublic
    enrolled_at: date

    model_config = {"from_attributes": True}


class BatchListResponse(BaseModel):
    items: list[BatchPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
