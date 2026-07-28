import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.examinations.evaluation.models import AttemptStatus


class StartExamAttemptRequest(BaseModel):
    student_id: uuid.UUID


class SubmitAnswerRequest(BaseModel):
    question_id: uuid.UUID
    answer_text: str | None = None


class GradeAnswerRequest(BaseModel):
    marks_awarded: int = Field(..., ge=0)


class ExamAttemptPublic(BaseModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    student_id: uuid.UUID
    started_at: datetime
    submitted_at: datetime | None
    total_score: int | None
    status: AttemptStatus

    model_config = {"from_attributes": True}


class ExamAnswerPublic(BaseModel):
    id: uuid.UUID
    attempt_id: uuid.UUID
    question_id: uuid.UUID
    answer_text: str | None
    marks_awarded: int | None
    evaluated_by_user_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
