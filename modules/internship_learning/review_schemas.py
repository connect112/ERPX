import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from modules.internship_learning.project_models import SubmissionMethod


class ReviewRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    # {factor id: marks} when the project has review factors; otherwise one ``score`` out of the project's total.
    factor_scores: dict[str, float] | None = None
    score: float | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=8000)

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Please name the review, for example Mid-way review.")
        return value


class ReviewOut(BaseModel):
    id: uuid.UUID
    label: str
    reviewer_name: str | None = None
    factor_scores: dict | None = None
    total: float
    max_total: int
    feedback: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewRow(BaseModel):
    """A student who handed in a project, with the reviews written for it and the final result."""

    selection_id: uuid.UUID
    student_name: str
    student_email: str
    method: SubmissionMethod
    submitted_at: datetime
    is_late: bool
    reviews: list[ReviewOut] = []
    average: float | None = None
    max_marks: int
    final_marks: float | None = None
    final_feedback: str | None = None
    final_published_at: datetime | None = None


class FinalRequest(BaseModel):
    # Leave empty to use the average of the reviews.
    final_marks: float | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=8000)


# ---------------- awards ----------------


class AwardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Please name the award.")
        return value


class AwardUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class GrantRequest(BaseModel):
    selection_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class GrantOut(BaseModel):
    selection_id: uuid.UUID
    student_name: str
    student_email: str
    note: str | None = None
    granted_at: datetime


class AwardOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    grants: list[GrantOut] = []


class MyAward(BaseModel):
    id: uuid.UUID
    internship_id: uuid.UUID
    internship_title: str
    name: str
    description: str | None = None
    note: str | None = None
    granted_at: datetime
