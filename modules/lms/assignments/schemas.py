import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.lms.assignments.models import SubmissionStatus


class AssignmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    due_date: datetime | None = None
    max_score: int = Field(default=100, ge=1)


class AssignmentUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    max_score: int | None = Field(default=None, ge=1)


class AssignmentPublic(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: str | None
    due_date: datetime | None
    max_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmissionCreateRequest(BaseModel):
    student_id: uuid.UUID
    content_url: str | None = None
    content_text: str | None = None


class MySubmissionCreateRequest(BaseModel):
    """Student self-service submission — no `student_id` field, unlike
    `SubmissionCreateRequest` (the staff/on-behalf-of route). The caller's
    own student record is resolved via `get_current_student`, matching the
    ownership-inferred convention used by every other `/mine`- or `/me`-
    suffixed self-service endpoint in this codebase (e.g. placements'
    `/apply/me`)."""

    content_url: str | None = None
    content_text: str | None = None


class SubmissionGradeRequest(BaseModel):
    score: int = Field(..., ge=0)
    feedback: str | None = None


class SubmissionPublic(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    content_url: str | None
    content_text: str | None
    submitted_at: datetime
    status: SubmissionStatus
    score: int | None
    feedback: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmissionWithStudentPublic(SubmissionPublic):
    student_name: str


class MessageResponse(BaseModel):
    message: str
