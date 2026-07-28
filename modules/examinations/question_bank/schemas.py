import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.examinations.question_bank.models import Difficulty, QuestionType


class QuestionCreateRequest(BaseModel):
    course_id: uuid.UUID | None = None
    question_text: str = Field(..., min_length=2)
    question_type: QuestionType = QuestionType.MCQ
    options: list[str] | None = None
    correct_answer: str | None = None
    default_marks: int = Field(default=1, ge=1)
    difficulty: Difficulty = Difficulty.MEDIUM


class QuestionUpdateRequest(BaseModel):
    question_text: str | None = None
    options: list[str] | None = None
    correct_answer: str | None = None
    default_marks: int | None = Field(default=None, ge=1)
    difficulty: Difficulty | None = None


class QuestionPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    course_id: uuid.UUID | None
    question_text: str
    question_type: QuestionType
    options: list[str] | None
    correct_answer: str | None
    default_marks: int
    difficulty: Difficulty
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
