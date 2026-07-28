import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class VivaCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    exam_date: date
    panel_members: str | None = None
    total_marks: int = Field(default=50, ge=1)
    passing_marks: int = Field(default=20, ge=0)


class VivaUpdateRequest(BaseModel):
    title: str | None = None
    exam_date: date | None = None
    panel_members: str | None = None
    total_marks: int | None = Field(default=None, ge=1)
    passing_marks: int | None = Field(default=None, ge=0)


class VivaPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    exam_date: date
    panel_members: str | None
    total_marks: int
    passing_marks: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RecordVivaResultRequest(BaseModel):
    student_id: uuid.UUID
    score: int = Field(..., ge=0)
    remarks: str | None = None


class VivaResultPublic(BaseModel):
    id: uuid.UUID
    viva_id: uuid.UUID
    student_id: uuid.UUID
    score: int
    remarks: str | None
    evaluated_by_user_id: uuid.UUID | None
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
