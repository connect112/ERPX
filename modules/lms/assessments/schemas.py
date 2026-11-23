import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from modules.lms.assessments.models import AssessmentType, AttemptStatus


class AssessmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    assessment_type: AssessmentType = AssessmentType.QUIZ
    total_marks: int = Field(default=100, ge=1)
    passing_marks: int = Field(default=40, ge=0)
    duration_minutes: int | None = Field(default=None, ge=1)
    # Set to make this assessment ONE internship's: only that internship's students and staff reach it. Omit for a course-wide one.
    internship_id: uuid.UUID | None = None
    show_result: bool = True


class AssessmentUpdateRequest(BaseModel):
    title: str | None = None
    total_marks: int | None = Field(default=None, ge=1)
    passing_marks: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=1)
    is_published: bool | None = None
    show_result: bool | None = None


class AssessmentPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    internship_id: uuid.UUID | None = None
    title: str
    assessment_type: AssessmentType
    total_marks: int
    passing_marks: int
    duration_minutes: int | None
    is_published: bool
    show_result: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class StartAttemptRequest(BaseModel):
    # A student always takes an assessment as themselves (this is then ignored or must be their own id); staff recording for a student name them.
    student_id: uuid.UUID | None = None


class SubmitAttemptRequest(BaseModel):
    # Only staff may authorize a score by hand (an assessment with no questions); a student's score is always worked out on the server.
    score: int = Field(..., ge=0)


class AttemptPublic(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    started_at: datetime
    submitted_at: datetime | None
    score: int | None
    total_marks: int | None = None
    status: AttemptStatus
    # on staff attempt lists: whether the student's LMS access on the internship is current ("revoked" keeps their history, marked)
    access_status: str | None = None
    student_name: str | None = None

    model_config = {"from_attributes": True}


class QuestionCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    options: list[str] = Field(..., min_length=2, max_length=8)
    correct_indices: list[int] = Field(..., min_length=1)
    allow_multiple: bool = False
    marks: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def _valid(self):
        self.options = [o.strip() for o in self.options]
        if any(not o for o in self.options):
            raise ValueError("Every option needs some text.")
        if len(set(self.correct_indices)) != len(self.correct_indices) or any(not 0 <= i < len(self.options) for i in self.correct_indices):
            raise ValueError("The correct answers must be distinct options of the question.")
        if not self.allow_multiple and len(self.correct_indices) != 1:
            raise ValueError("A single-answer question has exactly one correct option.")
        return self


class QuestionUpdateRequest(QuestionCreateRequest):
    pass


class QuestionStaff(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    text: str
    options: list[str]
    correct_indices: list[int]
    allow_multiple: bool
    marks: int
    order_index: int

    model_config = {"from_attributes": True}


class QuestionOption(BaseModel):
    index: int
    text: str


class QuestionForStudent(BaseModel):
    """What a student sees while answering: never the correct options."""

    id: uuid.UUID
    text: str
    marks: int
    allow_multiple: bool
    options: list[QuestionOption]


class TakeState(BaseModel):
    attempt_id: uuid.UUID
    status: AttemptStatus
    remaining_seconds: int | None = None
    questions: list[QuestionForStudent] = []
    saved_answers: dict[str, list[int]] = {}


class SaveAnswersRequest(BaseModel):
    answers: dict[str, list[int]] = {}


class TakeResult(BaseModel):
    attempt_id: uuid.UUID
    status: AttemptStatus
    submitted_at: datetime | None = None
    # present only when the assessment shows results to students (or staff have recorded one)
    score: int | None = None
    total_marks: int | None = None
    passed: bool | None = None


class MessageResponse(BaseModel):
    message: str
