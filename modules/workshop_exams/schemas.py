import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from modules.workshop_exams.certificate_template import CertificateLayout
from modules.workshop_exams.models import WorkshopExamStatus

# Name and email are always asked, so an admin-defined field can't reuse them.
_RESERVED_KEYS = {"name", "email"}
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class MessageResponse(BaseModel):
    message: str


# ---- Admin: exam setup ----


class InfoField(BaseModel):
    """One extra question about each student on the registration form."""

    key: str
    label: str = Field(..., min_length=1, max_length=120)
    required: bool = True
    type: Literal["text", "phone", "select"] = "text"
    options: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("key")
    @classmethod
    def _valid_key(cls, v: str) -> str:
        if not _KEY_RE.match(v) or v in _RESERVED_KEYS:
            raise ValueError("Invalid field key.")
        return v

    @model_validator(mode="after")
    def _select_needs_options(self):
        self.options = [o.strip() for o in self.options if o.strip()]
        if self.type == "select" and len(self.options) < 2:
            raise ValueError("A dropdown field needs at least 2 options.")
        if self.type != "select":
            self.options = []
        return self


def _validate_info_fields(fields: list[InfoField]) -> list[InfoField]:
    keys = [f.key for f in fields]
    if len(keys) != len(set(keys)):
        raise ValueError("Field keys must be unique.")
    return fields


class ExamCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    workshop_id: uuid.UUID | None = None
    duration_minutes: int = Field(default=30, ge=1, le=480)
    show_result: bool = False
    certificate_heading: str = Field(default="Certificate of Participation", max_length=255)
    certificate_text: str | None = None
    info_fields: list[InfoField] = Field(default_factory=list, max_length=12)

    _check_fields = field_validator("info_fields")(_validate_info_fields)


class ExamUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=480)
    show_result: bool | None = None
    certificate_heading: str | None = Field(default=None, max_length=255)
    certificate_text: str | None = None
    # Only ever set via the dedicated field so "leave unchanged" (omitted)
    # and "clear it" (explicit null) stay distinguishable -- see routes.
    certificate_release_at: datetime | None = None
    info_fields: list[InfoField] | None = Field(default=None, max_length=12)
    certificate_layout: CertificateLayout | None = None

    @field_validator("info_fields")
    @classmethod
    def _check_fields(cls, v):
        return _validate_info_fields(v) if v is not None else v


class SendCertificatesRequest(BaseModel):
    # Submit students who are still inside their time limit as they stand.
    include_in_progress: bool = False


class CertificatePreviewRequest(BaseModel):
    # Omitted = use the saved layout; sent = preview an unsaved one.
    layout: CertificateLayout | None = None


class CertificateTestEmailRequest(CertificatePreviewRequest):
    email: EmailStr


class ExamStatusRequest(BaseModel):
    status: WorkshopExamStatus


class ExamPublicAdmin(BaseModel):
    id: uuid.UUID
    workshop_id: uuid.UUID | None
    title: str
    description: str | None
    duration_minutes: int
    status: WorkshopExamStatus
    show_result: bool
    public_code: str
    info_fields: list[InfoField]
    certificate_release_at: datetime | None
    certificates_dispatched_at: datetime | None
    certificate_heading: str
    certificate_text: str | None
    has_certificate_template: bool = False
    certificate_layout: CertificateLayout | None = None
    question_count: int = 0
    attendee_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionInput(BaseModel):
    text: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=2, max_length=8)
    correct_indices: list[int] = Field(..., min_length=1)
    # False = "multiple choice" (exactly one right answer, radio buttons);
    # True = "checkboxes" (one or more right answers, all must be picked).
    allow_multiple: bool = False
    marks: int = Field(default=1, ge=1, le=100)

    @field_validator("options")
    @classmethod
    def _non_blank(cls, v: list[str]) -> list[str]:
        cleaned = [o.strip() for o in v]
        if any(not o for o in cleaned):
            raise ValueError("Options can't be blank.")
        if len({o.lower() for o in cleaned}) != len(cleaned):
            raise ValueError("Options must be different from each other.")
        return cleaned

    @model_validator(mode="after")
    def _answer_key_is_consistent(self):
        indices = sorted(set(self.correct_indices))
        if len(indices) != len(self.correct_indices):
            raise ValueError("Duplicate correct answers.")
        if indices[-1] >= len(self.options) or indices[0] < 0:
            raise ValueError("A correct answer points at an option that doesn't exist.")
        if not self.allow_multiple and len(indices) != 1:
            raise ValueError("A single-answer question needs exactly one correct option.")
        self.correct_indices = indices
        return self


class QuestionsAddRequest(BaseModel):
    questions: list[QuestionInput] = Field(..., min_length=1, max_length=500)


class QuestionAdmin(BaseModel):
    id: uuid.UUID
    text: str
    options: list[str]
    correct_indices: list[int]
    allow_multiple: bool
    marks: int
    order_index: int

    model_config = {"from_attributes": True}


class AttendeeInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class AttendeesImportRequest(BaseModel):
    attendees: list[AttendeeInput] = Field(..., min_length=1, max_length=2000)


class AttendeesImportResponse(BaseModel):
    added: int
    skipped_duplicates: int


class AttendeeAdmin(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    info: dict[str, str]
    invited_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    score: int | None
    total_marks: int | None
    certificate_number: str | None
    certificate_sent_at: datetime | None

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    total_attendees: int
    invited: int
    not_started: int
    in_progress: int
    submitted: int
    certificates_sent: int
    average_score_percent: float | None
    attendees: list[AttendeeAdmin]


class InvitesRequest(BaseModel):
    resend_all: bool = False


class InvitesResponse(BaseModel):
    queued: int


# ---- Public: registration (shared link) ----


class PublicJoinInfo(BaseModel):
    title: str
    description: str | None
    duration_minutes: int
    question_count: int
    info_fields: list[InfoField]
    # open | not_open | closed
    state: str


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    info: dict[str, str] = Field(default_factory=dict)


class RegisterResponse(BaseModel):
    # The attendee's personal link token -- absent when that email had
    # already registered (the link is re-sent by email instead, so typing
    # someone else's address never hands over their attempt).
    token: str | None = None
    already_registered: bool = False


# ---- Public: taking the exam (token flow) ----


class PublicQuestionOption(BaseModel):
    index: int
    text: str


class PublicQuestion(BaseModel):
    id: uuid.UUID
    text: str
    marks: int
    allow_multiple: bool
    options: list[PublicQuestionOption]


class PublicExamInfo(BaseModel):
    title: str
    description: str | None
    attendee_name: str
    duration_minutes: int
    question_count: int
    # not_open | ready | in_progress | submitted | closed
    state: str
    remaining_seconds: int | None = None
    score: int | None = None
    total_marks: int | None = None


class PublicStartResponse(BaseModel):
    remaining_seconds: int
    questions: list[PublicQuestion]
    saved_answers: dict[str, list[int]]


class AnswersRequest(BaseModel):
    answers: dict[str, list[int]] = Field(default_factory=dict)


class PublicSubmitResponse(BaseModel):
    submitted: bool
    score: int | None = None
    total_marks: int | None = None


class CertificateVerification(BaseModel):
    valid: bool
    attendee_name: str | None = None
    exam_title: str | None = None
    issued_at: datetime | None = None
