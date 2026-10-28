"""
Email Studio -- designed emails, their versions, the brand and signature they use, shared components, which ERPX email each
template stands in for, uploaded images, and the history of what was sent.

The built-in wording and the older Markdown edits (`modules/email_templates`) are left exactly as they were; a studio template
only takes over an ERPX email when an administrator assigns it (``EmailTemplateAssignment``) and has published it.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.db.base_model import TimestampedBase


class SourceType(str, enum.Enum):
    VISUAL = "visual"  # designed in the React Email visual editor; the editor's JSON is kept
    HTML = "html"  # imported HTML, edited as source
    CODE = "code"  # an approved React Email component, edited through its declared properties
    REACT = "react"  # React Email source pasted by an administrator, read (never run) into email HTML


class TemplateStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class VersionState(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class SendStatus(str, enum.Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class EmailAsset(TimestampedBase):
    """An image uploaded for emails. Email clients fetch it without signing in, so it is served from a public link."""

    __tablename__ = "email_studio_assets"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmailBrandProfile(TimestampedBase):
    __tablename__ = "email_brand_profiles"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_studio_assets.id", ondelete="SET NULL"), nullable=True)
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#2563eb", server_default="#2563eb")
    secondary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#1e40af", server_default="#1e40af")
    accent_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#f59e0b", server_default="#f59e0b")
    background_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#f4f4f5", server_default="#f4f4f5")
    text_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#111827", server_default="#111827")
    website: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    phone: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    address: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    tagline: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    social_links: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    # What recipients see as the sender's name and where replies go. The sending address itself stays the one the mail
    # provider is set up for.
    from_name: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    reply_to: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmailSignature(TimestampedBase):
    __tablename__ = "email_signatures"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="company", server_default="company")  # company | individual
    person_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    designation: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    phone: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    website: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_studio_assets.id", ondelete="SET NULL"), nullable=True)
    # An image of the signature supplied and approved by an administrator. Never generated or altered here.
    signature_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_studio_assets.id", ondelete="SET NULL"), nullable=True)
    signature_approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    signature_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    style: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")  # font_size, color, align
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmailComponent(TimestampedBase):
    """A reusable block (header, footer, button, notice...) kept as sanitised email HTML with placeholders."""

    __tablename__ = "email_components"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    html: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmailStudioTemplate(TimestampedBase):
    __tablename__ = "email_studio_templates"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="Custom Emails", server_default="Custom Emails")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    module: Mapped[str | None] = mapped_column(String(60), nullable=True)  # the ERPX module it is meant for
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TemplateStatus.DRAFT.value, server_default=TemplateStatus.DRAFT.value)
    # The version normal sending uses. Only a published version ever reaches a recipient.
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_studio_versions.id", ondelete="SET NULL", use_alter=True, name="fk_email_template_published_version"), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # A system template can never be deleted; this flag decides that, not the template's name.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    # Deleting hides a template and keeps everything (versions, send history, the audit trail); it can be restored.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmailStudioVersion(TimestampedBase):
    """One version of a template. A published version never changes; edits go into a draft version."""

    __tablename__ = "email_studio_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_email_version_number"),
        Index("uq_email_version_one_draft", "template_id", unique=True, postgresql_where=text("state = 'draft'")),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("email_studio_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=VersionState.DRAFT.value, server_default=VersionState.DRAFT.value)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    preheader: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    # visual: the editor's document, so the design can be reopened and edited
    editor_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # html: the source exactly as imported (never sent), kept apart from the sanitised copy below
    html_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    # react: the React Email source exactly as pasted (never run, never sent); body_html is built from it on every save
    react_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    # what is sent: sanitised email HTML (still holding {{placeholders}}) and its plain-text twin
    body_html: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # code: which approved component, and the values of its declared properties
    code_template_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    code_props: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    brand_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_brand_profiles.id", ondelete="SET NULL"), nullable=True)
    signature_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_signatures.id", ondelete="SET NULL"), nullable=True)
    # attachments: [{"kind": "recipient", "name": "offer_letter", "required": true} | {"kind": "shared", "asset": "<file id>"}]
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailTemplateAssignment(TimestampedBase):
    """Which studio template an ERPX email (a key of the built-in list) uses: for the organisation, or for one hackathon."""

    __tablename__ = "email_template_assignments"
    __table_args__ = (
        Index("uq_email_assignment_org", "organization_id", "key", unique=True, postgresql_where=text("hackathon_id IS NULL")),
        Index("uq_email_assignment_hackathon", "organization_id", "key", "hackathon_id", unique=True, postgresql_where=text("hackathon_id IS NOT NULL")),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    hackathon_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("email_studio_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class EmailSendRecord(TimestampedBase):
    """One email that went out (or failed): which template version made it, to whom, and how it ended. No message body and no
    links are kept, so sign-in and reset tokens never end up here."""

    __tablename__ = "email_send_records"
    __table_args__ = (
        Index("ix_email_send_records_org_created", "organization_id", "created_at"),
        Index("uq_email_send_idempotency", "organization_id", "idempotency_key", unique=True, postgresql_where=text("idempotency_key IS NOT NULL")),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    key: Mapped[str | None] = mapped_column(String(80), nullable=True)  # the ERPX email (template key) when known
    module: Mapped[str | None] = mapped_column(String(60), nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_studio_templates.id", ondelete="SET NULL"), nullable=True)
    version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_studio_versions.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # visual | html | code | markdown | default
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SendStatus.QUEUED.value, server_default=SendStatus.QUEUED.value)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachments: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sent_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
