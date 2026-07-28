import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.examinations.exams.models import ExamStatus


class ExamCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    exam_date: datetime
    duration_minutes: int = Field(default=60, ge=1)
    passing_marks: int = Field(default=40, ge=0)


class ExamUpdateRequest(BaseModel):
    title: str | None = None
    exam_date: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1)
    passing_marks: int | None = Field(default=None, ge=0)
    status: ExamStatus | None = None


class ExamPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    exam_date: datetime
    duration_minutes: int
    passing_marks: int
    status: ExamStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ExamWithTotalMarks(ExamPublic):
    total_marks: int


class AddQuestionToExamRequest(BaseModel):
    question_id: uuid.UUID
    marks_allocated: int = Field(..., ge=1)
    order_index: int = Field(..., ge=0)


class ExamQuestionPublic(BaseModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    question_id: uuid.UUID
    marks_allocated: int
    order_index: int

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
