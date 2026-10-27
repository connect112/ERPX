import re
import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.internship_learning.project_models import ProjectStatus, SubmissionMethod
from modules.internship_learning.schemas import FileOut

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean_url(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or " " in value:
        raise ValueError("Please enter a full web address starting with http:// or https://")
    return value


class ReferenceLink(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=255)
    url: str = Field(max_length=500)

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        return clean_url(value)


class ProjectFields(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    objectives: str | None = Field(default=None, max_length=8000)
    rules: str | None = Field(default=None, max_length=8000)
    submission_instructions: str | None = Field(default=None, max_length=8000)
    reference_links: list[ReferenceLink] = Field(default_factory=list, max_length=30)
    allow_file: bool = True
    allow_email: bool = False
    allow_repository: bool = False
    submission_email: str | None = Field(default=None, max_length=255)
    max_files: int = Field(default=5, ge=1, le=20)
    capacity: int | None = Field(default=None, ge=1, le=100000)
    starts_at: datetime | None = None
    deadline_at: datetime | None = None
    allow_late: bool = False

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Please enter a title.")
        return value

    @field_validator("submission_email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        value = (value or "").strip().lower()
        if not value:
            return None
        if not _EMAIL.match(value):
            raise ValueError("Please enter a valid email address.")
        return value


class ProjectCreateRequest(ProjectFields):
    pass


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=8000)
    objectives: str | None = Field(default=None, max_length=8000)
    rules: str | None = Field(default=None, max_length=8000)
    submission_instructions: str | None = Field(default=None, max_length=8000)
    reference_links: list[ReferenceLink] | None = Field(default=None, max_length=30)
    allow_file: bool | None = None
    allow_email: bool | None = None
    allow_repository: bool | None = None
    submission_email: str | None = Field(default=None, max_length=255)
    max_files: int | None = Field(default=None, ge=1, le=20)
    capacity: int | None = Field(default=None, ge=1, le=100000)
    starts_at: datetime | None = None
    deadline_at: datetime | None = None
    allow_late: bool | None = None
    status: ProjectStatus | None = None

    @field_validator("submission_email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        value = (value or "").strip().lower()
        if not value:
            return None
        if not _EMAIL.match(value):
            raise ValueError("Please enter a valid email address.")
        return value


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    internship_id: uuid.UUID
    title: str
    description: str | None
    objectives: str | None
    rules: str | None
    submission_instructions: str | None
    reference_links: list[dict]
    allow_file: bool
    allow_email: bool
    allow_repository: bool
    submission_email: str | None
    max_files: int
    capacity: int | None
    starts_at: datetime | None
    deadline_at: datetime | None
    allow_late: bool
    status: ProjectStatus
    created_at: datetime
    documents: list[FileOut] = []
    templates: list[FileOut] = []
    chosen_count: int = 0
    submitted_count: int = 0


class ProjectSelectionRow(BaseModel):
    """One enrolled student: the project they chose (if any) and what they handed in."""

    selection_id: uuid.UUID
    student_name: str
    student_email: str
    project_id: uuid.UUID | None = None
    project_title: str | None = None
    chosen_at: datetime | None = None
    submitted: bool = False
    method: SubmissionMethod | None = None
    submitted_at: datetime | None = None
    is_late: bool = False
    resubmission_count: int = 0
    repository_url: str | None = None
    note: str | None = None
    files: list[FileOut] = []
    received_at: datetime | None = None


class ReceivedRequest(BaseModel):
    received: bool = True


# ---------------- student side ----------------


class MyProjectSubmission(BaseModel):
    method: SubmissionMethod
    repository_url: str | None
    note: str | None
    submitted_at: datetime
    is_late: bool
    files: list[FileOut]
    received_at: datetime | None = None


class MyProject(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    objectives: str | None
    rules: str | None
    submission_instructions: str | None
    reference_links: list[dict]
    allow_file: bool
    allow_email: bool
    allow_repository: bool
    submission_email: str | None
    max_files: int
    starts_at: datetime | None
    deadline_at: datetime | None
    allow_late: bool
    status: ProjectStatus
    documents: list[FileOut] = []
    templates: list[FileOut] = []
    spots_left: int | None = None
    chosen_by_me: bool = False
    can_choose: bool = False
    can_submit: bool = False
    submission: MyProjectSubmission | None = None
