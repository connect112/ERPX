import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class PracticalCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    exam_date: date
    rubric: str | None = None
    total_marks: int = Field(default=100, ge=1)
    passing_marks: int = Field(default=40, ge=0)


class PracticalUpdateRequest(BaseModel):
    title: str | None = None
    exam_date: date | None = None
    rubric: str | None = None
    total_marks: int | None = Field(default=None, ge=1)
    passing_marks: int | None = Field(default=None, ge=0)


class PracticalPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    exam_date: date
    rubric: str | None
    total_marks: int
    passing_marks: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RecordPracticalResultRequest(BaseModel):
    student_id: uuid.UUID
    score: int = Field(..., ge=0)
    remarks: str | None = None


class PracticalResultPublic(BaseModel):
    id: uuid.UUID
    practical_id: uuid.UUID
    student_id: uuid.UUID
    score: int
    remarks: str | None
    evaluated_by_user_id: uuid.UUID | None
    evaluated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
