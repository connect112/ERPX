import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.internship_learning.models import AssignmentStatus


class MessageResponse(BaseModel):
    message: str


class FileOut(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    url: str | None = None
    created_at: datetime | None = None


class AssignmentTask(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=255)
    details: str | None = Field(default=None, max_length=4000)


class RubricRule(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    criterion: str = Field(min_length=1, max_length=255)
    points: int = Field(ge=1, le=1000)


class AssignmentFields(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    tasks: list[AssignmentTask] = Field(default_factory=list, max_length=50)
    instructions: str | None = Field(default=None, max_length=8000)
    max_marks: int = Field(default=100, ge=1, le=1000)
    rubric: list[RubricRule] = Field(default_factory=list, max_length=30)
    starts_at: datetime | None = None
    deadline_at: datetime | None = None
    allow_late: bool = False
    max_files: int = Field(default=5, ge=1, le=20)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Please enter a title.")
        return value


class AssignmentCreateRequest(AssignmentFields):
    pass


class AssignmentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    tasks: list[AssignmentTask] | None = Field(default=None, max_length=50)
    instructions: str | None = Field(default=None, max_length=8000)
    max_marks: int | None = Field(default=None, ge=1, le=1000)
    rubric: list[RubricRule] | None = Field(default=None, max_length=30)
    starts_at: datetime | None = None
    deadline_at: datetime | None = None
    allow_late: bool | None = None
    max_files: int | None = Field(default=None, ge=1, le=20)
    status: AssignmentStatus | None = None


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    internship_id: uuid.UUID
    title: str
    description: str | None
    tasks: list[dict]
    instructions: str | None
    max_marks: int
    rubric: list[dict]
    starts_at: datetime | None
    deadline_at: datetime | None
    allow_late: bool
    max_files: int
    status: AssignmentStatus
    created_at: datetime
    files: list[FileOut] = []
    submitted_count: int = 0
    graded_count: int = 0
    enrolled_count: int = 0


class SubmissionRow(BaseModel):
    """One enrolled student against one assignment (``submitted`` False when nothing has been handed in yet)."""

    selection_id: uuid.UUID
    student_name: str
    student_email: str
    submitted: bool
    submitted_at: datetime | None = None
    is_late: bool = False
    resubmission_count: int = 0
    note: str | None = None
    files: list[FileOut] = []
    rubric_scores: dict | None = None
    score: float | None = None
    feedback: str | None = None
    reviewed_at: datetime | None = None


class GradeRequest(BaseModel):
    # {rubric rule id: marks}; leave empty for an assignment without a rubric and give ``score`` instead.
    rubric_scores: dict[str, float] | None = None
    score: float | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=8000)


# ---------------- exams ----------------


class ExamSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    duration_minutes: int
    question_count: int
    attendee_count: int
    submitted_count: int
    average_percent: float | None = None


class AvailableExam(BaseModel):
    id: uuid.UUID
    title: str
    status: str


class ExamAssignRequest(BaseModel):
    send_invites: bool = True


class ExamAssignResponse(BaseModel):
    added: int
    already_on_exam: int
    invited: int


class ExamResultRow(BaseModel):
    selection_id: uuid.UUID
    student_name: str
    student_email: str
    state: str  # not_assigned | not_started | in_progress | submitted
    score: int | None = None
    total_marks: int | None = None
    percent: float | None = None
    submitted_at: datetime | None = None


# ---------------- student side ----------------


class MyInternship(BaseModel):
    id: uuid.UUID
    selection_id: uuid.UUID
    title: str
    description: str | None
    status: str
    open_assignments: int = 0
    open_exams: int = 0


class MyExam(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    duration_minutes: int
    status: str
    state: str  # not_started | in_progress | submitted
    url: str
    score: int | None = None
    total_marks: int | None = None
    submitted_at: datetime | None = None


class MySubmission(BaseModel):
    submitted_at: datetime
    is_late: bool
    note: str | None
    files: list[FileOut]
    reviewed: bool
    score: float | None = None
    rubric_scores: dict | None = None
    feedback: str | None = None
    can_resubmit: bool = False


class MyAssignment(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    tasks: list[dict]
    instructions: str | None
    max_marks: int
    rubric: list[dict]
    starts_at: datetime | None
    deadline_at: datetime | None
    allow_late: bool
    max_files: int
    status: AssignmentStatus
    files: list[FileOut] = []
    can_submit: bool = False
    submission: MySubmission | None = None
