import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from modules.our_internships.models import InternshipScope, OurInternshipStatus


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
    # Their standing in each event of the internship's scope they are registered for.
    standings: list[StudentPerformance]


class SelectedListResponse(BaseModel):
    items: list[SelectedStudent]
    total: int
