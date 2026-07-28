import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.lms.assessments.models import AssessmentType, AttemptStatus


class AssessmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    assessment_type: AssessmentType = AssessmentType.QUIZ
    total_marks: int = Field(default=100, ge=1)
    passing_marks: int = Field(default=40, ge=0)
    duration_minutes: int | None = Field(default=None, ge=1)


class AssessmentUpdateRequest(BaseModel):
    title: str | None = None
    total_marks: int | None = Field(default=None, ge=1)
    passing_marks: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=1)
    is_published: bool | None = None


class AssessmentPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    assessment_type: AssessmentType
    total_marks: int
    passing_marks: int
    duration_minutes: int | None
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StartAttemptRequest(BaseModel):
    student_id: uuid.UUID


class SubmitAttemptRequest(BaseModel):
    score: int = Field(..., ge=0)


class AttemptPublic(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    started_at: datetime
    submitted_at: datetime | None
    score: int | None
    status: AttemptStatus

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
