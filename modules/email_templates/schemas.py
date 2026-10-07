from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class TemplateVariablePublic(BaseModel):
    name: str
    description: str
    sample: str


class TemplateSummary(BaseModel):
    key: str
    name: str
    category: str
    description: str
    when_sent: str
    has_attachment: bool = False
    event_scoped: bool = False
    # True when the wording has been edited (for an event: edited for that event).
    customised: bool = False
    # Event view only: no wording of its own, so the organisation's (edited or default) is used.
    inherited: bool = False
    updated_at: datetime | None = None
    updated_by_name: str | None = None


class TemplateDetail(TemplateSummary):
    subject: str
    body: str
    default_subject: str
    default_body: str
    variables: list[TemplateVariablePublic]
    required: list[str]


class TemplateSaveRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=300)
    body: str = Field(..., min_length=1, max_length=20000)

    _trim_subject = field_validator("subject", mode="before")(_strip)


class PreviewRequest(BaseModel):
    subject: str = Field(default="", max_length=300)
    body: str = Field(default="", max_length=20000)


class PreviewResponse(BaseModel):
    subject: str
    html: str
    text: str
    errors: list[str] = Field(default_factory=list)


class TestSendRequest(BaseModel):
    to_email: EmailStr
    # The draft being edited; leave both out to send the saved wording.
    subject: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=20000)


class TestSendResponse(BaseModel):
    sent: bool
    message: str
