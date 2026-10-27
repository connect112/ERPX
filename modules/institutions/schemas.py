import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from modules.institutions.models import InstitutionEventStatus, InstitutionEventType


def _trim(value):
    return " ".join(value.split()) if isinstance(value, str) else value


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class MessageResponse(BaseModel):
    message: str


# ---- institutions ----


class InstitutionCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    location: str = Field(..., min_length=2, max_length=255)
    mou_details: str | None = Field(default=None, max_length=20000)
    faculty_name: str = Field(..., min_length=2, max_length=255)
    faculty_designation: str | None = Field(default=None, max_length=255)
    faculty_email: EmailStr | None = None
    faculty_phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=20000)

    _trim_names = field_validator("name", "location", "faculty_name", "faculty_designation", "faculty_phone", mode="before")(_trim)
    _blank = field_validator("faculty_email", "mou_details", "notes", mode="before")(_blank_to_none)


class InstitutionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    location: str | None = Field(default=None, min_length=2, max_length=255)
    mou_details: str | None = Field(default=None, max_length=20000)
    faculty_name: str | None = Field(default=None, min_length=2, max_length=255)
    faculty_designation: str | None = Field(default=None, max_length=255)
    faculty_email: EmailStr | None = None
    faculty_phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=20000)

    _trim_names = field_validator("name", "location", "faculty_name", "faculty_designation", "faculty_phone", mode="before")(_trim)
    _blank = field_validator("faculty_email", "mou_details", "notes", mode="before")(_blank_to_none)


class InstitutionOut(BaseModel):
    id: uuid.UUID
    name: str
    location: str
    mou_details: str | None
    mou_filename: str | None
    mou_size_bytes: int | None
    faculty_name: str
    faculty_designation: str | None
    faculty_email: str | None
    faculty_phone: str | None
    notes: str | None
    event_count: int = 0
    student_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class InstitutionListResponse(BaseModel):
    items: list[InstitutionOut]
    total: int


# ---- events ----


class EventCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    event_type: InstitutionEventType = InstitutionEventType.WORKSHOP
    start_date: date
    end_date: date
    description: str | None = Field(default=None, max_length=20000)
    max_capacity: int | None = Field(default=None, ge=1, le=100000)
    status: InstitutionEventStatus = InstitutionEventStatus.UPCOMING

    _trim_name = field_validator("name", mode="before")(_trim)
    _blank = field_validator("description", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date.")
        return self


class EventUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    event_type: InstitutionEventType | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=20000)
    # Sent explicitly as null to remove the limit, so "omitted" and "no limit" stay different: see model_fields_set.
    max_capacity: int | None = Field(default=None, ge=1, le=100000)
    status: InstitutionEventStatus | None = None

    _trim_name = field_validator("name", mode="before")(_trim)
    _blank = field_validator("description", mode="before")(_blank_to_none)


class EventOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    institution_name: str = ""
    name: str
    event_type: InstitutionEventType
    start_date: date
    end_date: date
    description: str | None
    max_capacity: int | None
    status: InstitutionEventStatus
    student_count: int = 0
    exam_count: int = 0
    hackathon_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- students ----


class StudentFields(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    details: dict[str, str] = Field(default_factory=dict)

    _trim_name = field_validator("name", "phone", mode="before")(_trim)

    @field_validator("details")
    @classmethod
    def _small_details(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 30:
            raise ValueError("Too many extra fields.")
        return {_trim(k)[:60]: _trim(v)[:255] for k, v in value.items() if _trim(k) and _trim(v)}


class StudentCreateRequest(StudentFields):
    pass


class StudentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    details: dict[str, str] | None = None

    _trim_name = field_validator("name", "phone", mode="before")(_trim)

    @field_validator("details")
    @classmethod
    def _small_details(cls, value):
        if value is None:
            return value
        if len(value) > 30:
            raise ValueError("Too many extra fields.")
        return {_trim(k)[:60]: _trim(v)[:255] for k, v in value.items() if _trim(k) and _trim(v)}


class StudentEventRef(BaseModel):
    event_id: uuid.UUID
    event_name: str
    event_type: InstitutionEventType
    status: InstitutionEventStatus


class StudentOut(BaseModel):
    id: uuid.UUID
    institution_id: uuid.UUID
    institution_name: str = ""
    name: str
    email: str
    phone: str | None
    details: dict[str, str]
    events: list[StudentEventRef] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentListResponse(BaseModel):
    items: list[StudentOut]
    total: int


class EventStudentOut(BaseModel):
    """A student as registered for one event: who they are, plus that event's individual score and remarks."""

    student_id: uuid.UUID
    institution_id: uuid.UUID
    institution_name: str
    event_id: uuid.UUID
    event_name: str
    name: str
    email: str
    phone: str | None
    details: dict[str, str]
    individual_score: float | None
    remarks: str | None
    registered_at: datetime


class EventStudentListResponse(BaseModel):
    items: list[EventStudentOut]
    total: int


class RegistrationUpdateRequest(BaseModel):
    individual_score: float | None = Field(default=None, ge=0, le=9999)
    remarks: str | None = Field(default=None, max_length=5000)

    _blank = field_validator("remarks", mode="before")(_blank_to_none)


class RegisterStudentsRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=5000)


class ImportTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5_000_000)


class ImportProblem(BaseModel):
    row: int
    reason: str
    raw: str


class ImportResult(BaseModel):
    dry_run: bool
    total_rows: int
    new_students: int
    existing_students: int
    registered: int
    already_registered: int
    over_capacity: int
    problems: list[ImportProblem]


# ---- activities linked to an event ----


class LinkedExam(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    attendee_count: int = 0
    question_count: int = 0
    event_id: uuid.UUID | None = None


class LinkedHackathon(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    status: str
    start_date: date
    end_date: date
    event_id: uuid.UUID | None = None


class CandidateSource(BaseModel):
    kind: str  # exam | hackathon
    title: str


class StudentCandidate(BaseModel):
    """One person found in the linked exams and hackathons, combined by email, waiting to be verified."""

    email: str
    name: str
    phone: str | None = None
    name_variants: list[str] = []
    sources: list[CandidateSource] = []
    entries: int
    status: str  # new | at_institution | registered
    existing_name: str | None = None
    issues: list[str] = []  # invalid_email | name_variants | name_differs
    addable: bool


class NoEmailEntry(BaseModel):
    name: str
    source: CandidateSource


class CandidatesOut(BaseModel):
    exams: int
    hackathons: int
    candidates: list[StudentCandidate]
    without_email: list[NoEmailEntry]
    message: str


class CandidateItem(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)


class CandidatesAddRequest(BaseModel):
    items: list[CandidateItem] = Field(min_length=1, max_length=2000)


class CandidatesAddOut(BaseModel):
    new_students: int
    registered: int
    skipped: int
    message: str
