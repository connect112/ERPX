import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from modules.our_internships.models import InternshipScope, OfferStatus, OurInternshipStatus
from modules.our_internships.offer_letter import OfferLayout


def _trim(value):
    return " ".join(value.split()) if isinstance(value, str) else value


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class MessageResponse(BaseModel):
    message: str


# ---- the internship itself ----


class InternshipCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    scope: InternshipScope
    # For a specific institution: which one, and optionally one of its events (leave empty for all of its events).
    institution_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None

    _trim_title = field_validator("title", mode="before")(_trim)
    _blank = field_validator("description", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def _scope_matches(self):
        if self.scope == InternshipScope.INSTITUTION and self.institution_id is None:
            raise ValueError("Choose the institution to select students from.")
        if self.scope == InternshipScope.ALL and (self.institution_id or self.event_id):
            raise ValueError("Selecting from all students does not take an institution or event.")
        return self


class InternshipUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    status: OurInternshipStatus | None = None

    _trim_title = field_validator("title", mode="before")(_trim)
    _blank = field_validator("description", mode="before")(_blank_to_none)


class InternshipOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    scope: InternshipScope
    institution_id: uuid.UUID | None
    institution_name: str | None = None
    event_id: uuid.UUID | None
    event_name: str | None = None
    status: OurInternshipStatus
    selected_count: int = 0
    offers_released_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- performance ----


class ExamInfo(BaseModel):
    id: uuid.UUID
    title: str
    event_id: uuid.UUID
    total_marks: int


class HackathonInfo(BaseModel):
    id: uuid.UUID
    title: str
    event_id: uuid.UUID
    max_total: int


class ExamMark(BaseModel):
    exam_id: uuid.UUID
    title: str
    attended: bool
    score: int | None = None
    total_marks: int | None = None


class TeamRef(BaseModel):
    team_id: uuid.UUID
    team_name: str
    hackathon_id: uuid.UUID
    hackathon_title: str
    score: int
    max_total: int
    rank: int | None = None
    tasks_scored: int = 0


class StudentPerformance(BaseModel):
    """One student's standing in one event: registration details, exam marks, team and individual hackathon scores."""

    student_id: uuid.UUID
    name: str
    email: str
    phone: str | None
    details: dict[str, str] = Field(default_factory=dict)
    institution_id: uuid.UUID
    institution_name: str
    event_id: uuid.UUID
    event_name: str
    individual_score: float | None = None
    remarks: str | None = None
    exams: list[ExamMark] = Field(default_factory=list)
    # Marks over the exams they sat; None if they sat none.
    exam_score: int | None = None
    exam_total: int | None = None
    exam_percent: float | None = None
    team: TeamRef | None = None
    selected: bool = False


class TeamMember(BaseModel):
    name: str
    email: str | None
    # None for a team member who is not on this event's registration list (cannot be selected from here).
    student_id: uuid.UUID | None = None
    exam_score: int | None = None
    exam_total: int | None = None
    individual_score: float | None = None
    selected: bool = False


class TeamPerformance(BaseModel):
    team_id: uuid.UUID | None
    team_name: str
    hackathon_id: uuid.UUID | None
    hackathon_title: str | None
    event_id: uuid.UUID
    event_name: str
    institution_name: str
    score: int | None
    max_total: int | None
    rank: int | None
    tasks_scored: int = 0
    members: list[TeamMember]


class PerformanceResponse(BaseModel):
    exams: list[ExamInfo]
    hackathons: list[HackathonInfo]
    students: list[StudentPerformance]
    teams: list[TeamPerformance]
    total_students: int


# ---- selection ----


class SelectRequest(BaseModel):
    student_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)

    _blank = field_validator("note", mode="before")(_blank_to_none)


class SelectionNoteRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)

    _blank = field_validator("note", mode="before")(_blank_to_none)


class SelectedStudent(BaseModel):
    student_id: uuid.UUID
    name: str
    email: str
    phone: str | None
    institution_id: uuid.UUID
    institution_name: str
    note: str | None
    selected_at: datetime
    offer_reference: str | None = None
    offer_status: OfferStatus = OfferStatus.NOT_SENT
    offer_sent_at: datetime | None = None
    offer_error: str | None = None
    # Their standing in each event of the internship's scope they are registered for.
    standings: list[StudentPerformance]


class SelectedListResponse(BaseModel):
    items: list[SelectedStudent]
    total: int


# ---- offer letters ----


class OfferSettings(BaseModel):
    """Everything that makes up the offer: the template, where details go on it, and the email."""

    has_template: bool
    template_filename: str | None
    template_pages: int | None
    template_size: int | None
    layout: OfferLayout | None
    email_subject: str
    email_body: str
    email_is_default: bool
    offer_date: date | None
    placeholders: dict[str, str]
    field_labels: dict[str, str]
    released_at: datetime | None
    # What still has to be done before offers can be released (empty when ready).
    missing: list[str]
    counts: dict[str, int]


class OfferEmailRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=20000)
    # The date printed on the letters; empty means the day they are released.
    offer_date: date | None = None

    @field_validator("subject", "body", mode="before")
    @classmethod
    def _blank_resets(cls, value):
        # an empty subject/body means "use the standard wording again"
        return value.strip() or None if isinstance(value, str) else value


class OfferPreviewRequest(BaseModel):
    layout: OfferLayout | None = None


class OfferReleaseRequest(BaseModel):
    # Release only these students (they must be on the selected list). Omitted: everyone not yet sent, and anyone whose
    # earlier send failed.
    student_ids: list[uuid.UUID] | None = Field(default=None, max_length=2000)
    # Also send again to students whose offer was already sent (an explicit choice, e.g. a corrected letter).
    resend: bool = False


class OfferReleaseResponse(BaseModel):
    queued: int
    already_sent: int
    message: str


class OfferTestEmailRequest(BaseModel):
    to_email: EmailStr
