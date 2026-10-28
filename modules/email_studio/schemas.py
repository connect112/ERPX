import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

SourceLiteral = Literal["visual", "html", "code", "react"]
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

CATEGORIES = (
    "Account Verification", "Password Reset", "Account Invitations", "Institution Communication", "Workshop Notifications",
    "Hackathon Notifications", "Internship Offer Letters", "Internship Onboarding", "Exams and Assignments", "Project Notifications",
    "Payment Confirmations", "Internship Certificates", "General Announcements", "Custom Emails",
)


def _no_break(value: str) -> str:
    if re.search(r"[\r\n\x00]", value or ""):
        raise ValueError("This cannot contain line breaks.")
    return (value or "").strip()


class DraftPayload(BaseModel):
    """What the editor saves. Which fields apply depends on the template's source type."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=60)
    module: str | None = Field(default=None, max_length=60)
    subject: str = Field(default="", max_length=300)
    preheader: str = Field(default="", max_length=200)
    editor_json: dict[str, Any] | None = None  # visual: the editor's document
    html: str | None = Field(default=None, max_length=700_000)  # visual: the editor's export; html: the source
    code_template_key: str | None = Field(default=None, max_length=80)
    code_props: dict[str, str] | None = None
    react_source: str | None = Field(default=None, max_length=200_000)  # react: the pasted React Email code
    brand_profile_id: uuid.UUID | None = None
    signature_id: uuid.UUID | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("subject")
    @classmethod
    def _subject(cls, value: str) -> str:
        return _no_break(value)

    @field_validator("category")
    @classmethod
    def _category(cls, value: str | None) -> str | None:
        if value is not None and value not in CATEGORIES:
            raise ValueError("Choose one of the listed categories.")
        return value


class CreatePayload(DraftPayload):
    name: str = Field(min_length=1, max_length=200)  # type: ignore[assignment]
    source_type: SourceLiteral
    category: str = "Custom Emails"  # type: ignore[assignment]


class PreviewContext(BaseModel):
    type: Literal["sample", "internship"] = "sample"
    key: str | None = None  # the ERPX email whose sample values to use
    internship_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None


class PreviewRequest(BaseModel):
    source_type: SourceLiteral
    draft: DraftPayload
    context: PreviewContext = Field(default_factory=PreviewContext)


class PreviewResponse(BaseModel):
    subject: str
    html: str
    text: str
    missing: list[str]
    warnings: list[str]
    unsupported: list[str]
    attachments: list[dict[str, Any]]


class TestRequest(PreviewRequest):
    to_email: EmailStr


class TestResponse(BaseModel):
    sent: bool
    message: str


class VersionOut(BaseModel):
    id: uuid.UUID
    version_number: int
    state: str
    subject: str
    created_by_name: str | None = None
    created_at: datetime
    published_by_name: str | None = None
    published_at: datetime | None = None
    brand_profile_id: uuid.UUID | None = None
    signature_id: uuid.UUID | None = None
    source_type: str


class DraftOut(BaseModel):
    version_id: uuid.UUID
    version_number: int
    state: str
    subject: str
    preheader: str
    editor_json: dict[str, Any] | None = None
    html_source: str | None = None
    react_source: str | None = None
    body_html: str
    code_template_key: str | None = None
    code_props: dict[str, str] | None = None
    brand_profile_id: uuid.UUID | None = None
    signature_id: uuid.UUID | None = None
    config: dict[str, Any]
    updated_at: datetime


class AssignmentOut(BaseModel):
    key: str
    name: str
    hackathon_id: uuid.UUID | None = None


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    category: str
    source_type: str
    module: str | None = None
    status: str
    published_version_id: uuid.UUID | None = None
    published_version_number: int | None = None
    has_draft: bool
    current: DraftOut  # the draft when there is one, otherwise the published version
    assignments: list[AssignmentOut]
    updated_at: datetime
    updated_by_name: str | None = None
    is_system: bool = False
    deleted_at: datetime | None = None


class LibraryItem(BaseModel):
    id: str  # a template id, or "system:<key>" for a built-in email
    key: str | None = None
    name: str
    description: str
    category: str
    creation_method: str
    source_type: str  # visual | html | code | markdown | default
    module: str | None = None
    status: str  # draft | published | archived | active
    updated_at: datetime | None = None
    updated_by_name: str | None = None
    is_system: bool
    assigned_to: list[str] = Field(default_factory=list)
    customised: bool = False
    has_attachment: bool = False
    has_draft: bool = False
    # Deleting: only templates you made can go, and not while an ERPX email uses them.
    can_delete: bool = False
    delete_blocked_reason: str | None = None
    used_by: list[AssignmentOut] = Field(default_factory=list)
    deleted_at: datetime | None = None
    deleted_by_name: str | None = None


class ReactIssue(BaseModel):
    severity: str  # error | warning
    message: str
    line: int | None = None
    column: int | None = None
    code: str = ""


class ReactBuildRequest(BaseModel):
    source: str = Field(max_length=200_000)
    preheader: str = Field(default="", max_length=200)


class ReactBuildResponse(BaseModel):
    ok: bool
    errors: list[ReactIssue]
    warnings: list[ReactIssue]
    html: str = ""
    text: str = ""
    title: str = ""
    preheader: str = ""
    placeholders: list[str] = Field(default_factory=list)
    unsupported_placeholders: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)


class AssignRequest(BaseModel):
    template_id: uuid.UUID
    hackathon_id: uuid.UUID | None = None


class PlaceholderOut(BaseModel):
    name: str
    group: str
    description: str
    sample: str


class CodeTemplateOut(BaseModel):
    key: str
    name: str
    description: str
    category: str
    module: str | None = None
    suggested_for: str | None = None
    subject: str
    placeholders: list[str]
    props: list[dict[str, Any]]


class BrandPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    company_name: str = Field(default="", max_length=200)
    logo_asset_id: uuid.UUID | None = None
    primary_color: str = "#2563eb"
    secondary_color: str = "#1e40af"
    accent_color: str = "#f59e0b"
    background_color: str = "#f4f4f5"
    text_color: str = "#111827"
    website: str = Field(default="", max_length=300)
    contact_email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=60)
    address: str = Field(default="", max_length=500)
    tagline: str = Field(default="", max_length=200)
    social_links: list[dict[str, str]] = Field(default_factory=list, max_length=10)
    from_name: str = Field(default="", max_length=120)
    reply_to: str = Field(default="", max_length=255)
    is_default: bool = False

    @field_validator("primary_color", "secondary_color", "accent_color", "background_color", "text_color")
    @classmethod
    def _colour(cls, value: str) -> str:
        if not _COLOR.match(value):
            raise ValueError("Use a colour like #2563eb.")
        return value.lower()

    @field_validator("website")
    @classmethod
    def _website(cls, value: str) -> str:
        value = value.strip()
        if value and not re.match(r"^https?://", value, re.I):
            raise ValueError("The website must start with http:// or https://")
        return value

    @field_validator("name", "company_name", "tagline", "from_name", "address", "phone")
    @classmethod
    def _single_line(cls, value: str) -> str:
        return _no_break(value) if value else value

    @field_validator("contact_email", "reply_to")
    @classmethod
    def _address(cls, value: str) -> str:
        value = _no_break(value)
        if value and not re.match(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$", value):
            raise ValueError("That is not a valid email address.")
        return value

    @field_validator("social_links")
    @classmethod
    def _social(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        out = []
        for item in value:
            label, url = (item.get("label") or "").strip(), (item.get("url") or "").strip()
            if label and re.match(r"^https?://", url, re.I):
                out.append({"label": label[:40], "url": url[:300]})
        return out


class BrandOut(BrandPayload):
    id: uuid.UUID
    logo_url: str | None = None
    updated_at: datetime


class SignaturePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scope: Literal["company", "individual"] = "company"
    person_name: str = Field(default="", max_length=200)
    designation: str = Field(default="", max_length=200)
    company_name: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=60)
    website: str = Field(default="", max_length=300)
    logo_asset_id: uuid.UUID | None = None
    signature_asset_id: uuid.UUID | None = None
    style: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False

    @field_validator("name", "person_name", "designation", "company_name", "phone")
    @classmethod
    def _single_line(cls, value: str) -> str:
        return _no_break(value) if value else value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = _no_break(value)
        if value and not re.match(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$", value):
            raise ValueError("That is not a valid email address.")
        return value

    @field_validator("website")
    @classmethod
    def _website(cls, value: str) -> str:
        value = value.strip()
        if value and not re.match(r"^https?://", value, re.I):
            raise ValueError("The website must start with http:// or https://")
        return value

    @field_validator("style")
    @classmethod
    def _style(cls, value: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if isinstance(value.get("color"), str) and _COLOR.match(value["color"]):
            out["color"] = value["color"].lower()
        if isinstance(value.get("font_size"), int) and 10 <= value["font_size"] <= 22:
            out["font_size"] = value["font_size"]
        if value.get("align") in ("left", "center", "right"):
            out["align"] = value["align"]
        return out


class SignatureOut(SignaturePayload):
    id: uuid.UUID
    signature_image_url: str | None = None
    logo_url: str | None = None
    signature_approved: bool = False
    updated_at: datetime


class ComponentPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["header", "footer", "button", "announcement", "info_card", "internship_details", "warning", "contact"]
    description: str = Field(default="", max_length=300)
    html: str = Field(min_length=1, max_length=60_000)


class ComponentOut(ComponentPayload):
    id: uuid.UUID
    updated_at: datetime


class AssetOut(BaseModel):
    id: uuid.UUID
    token: str
    filename: str
    content_type: str
    size_bytes: int
    url: str | None = None  # the public address, for images


class HistoryItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    recipient: str
    subject: str
    key: str | None = None
    module: str | None = None
    template_id: uuid.UUID | None = None
    template_name: str | None = None
    version_number: int | None = None
    source: str | None = None
    status: str
    error: str | None = None
    is_test: bool
    attachments: int


class MessageOut(BaseModel):
    message: str


class ApproveSignatureRequest(BaseModel):
    approve: bool = True
