"""
Email Studio: the library, template drafts and versions, publishing, assigning a template to an ERPX email, previews and tests.

A template is edited as a *draft*; only a published version is ever used for real emails, and publishing and assigning are
separate, deliberate steps. Nothing here sends mail except the explicit test send.
"""

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, RateLimitError, ValidationError
from modules.authentication.models import User
from modules.email_studio.code_templates import CodeTemplateError, list_code_templates, load_code_template
from modules.email_studio.react_import import build as build_react
from modules.email_studio.engine import Draft, MissingPlaceholders, render_draft
from modules.email_studio.models import (
    EmailBrandProfile,
    EmailSignature,
    EmailStudioTemplate,
    EmailStudioVersion,
    EmailTemplateAssignment,
    SourceType,
    TemplateStatus,
    VersionState,
)
from modules.email_studio.placeholders import (
    BRAND_NAMES,
    COMPONENT_NAMES,
    GROUP_ORDER,
    PlaceholderInfo,
    component_misuse,
    fill_props,
    group_of,
    placeholders_in,
    unsupported,
)
from modules.email_studio.schemas import (
    CATEGORIES,
    AssignmentOut,
    CodeTemplateOut,
    CreatePayload,
    DraftOut,
    DraftPayload,
    LibraryItem,
    PlaceholderOut,
    PreviewContext,
    ReactBuildResponse,
    ReactIssue,
    PreviewResponse,
    TemplateOut,
    VersionOut,
)
from modules.email_studio.sanitize import html_to_text, sanitize_document, validate_editor_json
from modules.email_templates.models import EmailTemplate
from packages.email.history import SendMeta, set_send_meta
from packages.email.registry import TEMPLATES, TemplateDef, get_def, sample_values
from packages.email.service import email_service

TEST_SENDS_PER_HOUR = 20
_recent_tests: dict[uuid.UUID, deque[float]] = defaultdict(deque)

_CATEGORY_OF_KEY = {
    "verification": "Account Verification",
    "password_reset": "Password Reset",
    "account_invite": "Account Invitations",
    "hackathon_participant_welcome": "Hackathon Notifications",
    "hackathon_winner_certificate": "Hackathon Notifications",
    "hackathon_participation_certificate": "Hackathon Notifications",
    "internship_offer_letter": "Internship Offer Letters",
    "internship_welcome": "Internship Onboarding",
    "internship_completion_certificate": "Internship Certificates",
    "internship_participation_certificate": "Internship Certificates",
    "workshop_exam_invite": "Workshop Notifications",
    "workshop_certificate": "Workshop Notifications",
    "announcement": "General Announcements",
    "payroll_draft_ready": "Payment Confirmations",
    "payslip_ready": "Payment Confirmations",
}
_METHOD = {"visual": "Visual editor", "html": "HTML import", "code": "React Email component", "react": "React Email code", "markdown": "Markdown (built-in)", "default": "Built-in"}


def sample_for(key: str | None) -> dict[str, str]:
    """Sample values for previews: one email's own samples, or every known placeholder's sample."""
    if key and get_def(key):
        return {**{n: "" for n in BRAND_NAMES}, **sample_values(get_def(key))}  # type: ignore[arg-type]
    out: dict[str, str] = {}
    for definition in TEMPLATES:
        for v in definition.variables:
            out.setdefault(v.name, v.sample)
    return out


def catalog(key: str | None = None) -> list[PlaceholderOut]:
    """The placeholders an admin can insert, grouped; for one ERPX email only the values that email supplies (plus the brand's)."""
    rows: dict[str, PlaceholderInfo] = {}
    sources = [get_def(key)] if key and get_def(key) else list(TEMPLATES)
    for definition in sources:
        assert definition is not None
        for v in definition.variables:
            rows.setdefault(v.name, PlaceholderInfo(v.name, group_of(v.name), v.description, v.sample))
    brand_info = {
        "company_name": "The brand's company name", "company_website": "The brand's website", "company_email": "The brand's contact email",
        "company_phone": "The brand's phone number", "company_address": "The brand's address", "brand_name": "The brand's name",
        "logo_url": "The address of the brand's logo", "authorized_signatory": "The signature's person", "authorized_designation": "The signature's designation",
        "current_year": "The current year",
    }
    for name in BRAND_NAMES:
        rows.setdefault(name, PlaceholderInfo(name, group_of(name), brand_info.get(name, name), ""))
    for name, desc in (("signature", "The chosen signature block"), ("brand_header", "The brand's header block"), ("brand_footer", "The brand's footer block")):
        rows[name] = PlaceholderInfo(name, "Company", desc + " (use once)", "")
    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    return [PlaceholderOut(name=r.name, group=r.group, description=r.description, sample=r.sample) for r in sorted(rows.values(), key=lambda r: (order.get(r.group, 99), r.name))]


def allowed_for_key(definition: TemplateDef | None) -> set[str] | None:
    return ({v.name for v in definition.variables} | set(BRAND_NAMES) | set(COMPONENT_NAMES)) if definition else None


def code_templates_out() -> list[CodeTemplateOut]:
    return [
        CodeTemplateOut(
            key=t.key, name=t.name, description=t.description, category=t.category, module=t.module, suggested_for=t.suggested_for, subject=t.subject,
            placeholders=list(t.placeholders),
            props=[{"name": p.name, "label": p.label, "type": p.type, "default": p.default, "required": p.required, "description": p.description} for p in t.props],
        )
        for t in list_code_templates()
    ]


class StudioService:
    def __init__(self, db: AsyncSession, organization_id: uuid.UUID):
        self.db = db
        self.organization_id = organization_id

    # ------------------------------------------------------------------ lookups

    async def _names(self, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
        wanted = {i for i in ids if i}
        if not wanted:
            return {}
        return dict((await self.db.execute(select(User.id, User.full_name).where(User.id.in_(wanted)))).all())

    async def template(self, template_id: uuid.UUID, include_deleted: bool = False) -> EmailStudioTemplate:
        row = await self.db.get(EmailStudioTemplate, template_id)
        if row is None or row.organization_id != self.organization_id or (row.deleted_at is not None and not include_deleted):
            raise NotFoundError("Email template", template_id)
        return row

    async def _draft(self, template_id: uuid.UUID) -> EmailStudioVersion | None:
        return (
            await self.db.execute(
                select(EmailStudioVersion).where(EmailStudioVersion.template_id == template_id, EmailStudioVersion.state == VersionState.DRAFT.value)
            )
        ).scalar_one_or_none()

    async def _version(self, template: EmailStudioTemplate, version_id: uuid.UUID) -> EmailStudioVersion:
        row = await self.db.get(EmailStudioVersion, version_id)
        if row is None or row.template_id != template.id:
            raise NotFoundError("Version", version_id)
        return row

    async def _next_number(self, template_id: uuid.UUID) -> int:
        top = (await self.db.execute(select(func.max(EmailStudioVersion.version_number)).where(EmailStudioVersion.template_id == template_id))).scalar_one()
        return (top or 0) + 1

    # ------------------------------------------------------------------ library

    async def library(self) -> list[LibraryItem]:
        templates = list(
            (await self.db.execute(select(EmailStudioTemplate).where(EmailStudioTemplate.organization_id == self.organization_id, EmailStudioTemplate.deleted_at.is_(None)))).scalars().all()
        )
        assigns = list((await self.db.execute(select(EmailTemplateAssignment).where(EmailTemplateAssignment.organization_id == self.organization_id))).scalars().all())
        drafts = {r for r in (await self.db.execute(select(EmailStudioVersion.template_id).where(EmailStudioVersion.organization_id == self.organization_id, EmailStudioVersion.state == VersionState.DRAFT.value))).scalars().all()}
        names = await self._names({t.updated_by_user_id for t in templates})
        overrides = list((await self.db.execute(select(EmailTemplate).where(EmailTemplate.organization_id == self.organization_id, EmailTemplate.hackathon_id.is_(None)))).scalars().all())
        by_template: dict[uuid.UUID, list[str]] = defaultdict(list)
        by_key: dict[str, uuid.UUID] = {}
        for a in assigns:
            by_template[a.template_id].append(a.key)
            if a.hackathon_id is None:
                by_key[a.key] = a.template_id
        by_id = {t.id: t for t in templates}
        items: list[LibraryItem] = []
        for t in templates:
            used = sorted(by_template.get(t.id, []))
            can_delete, blocked = self.delete_rule(t, used)
            items.append(
                LibraryItem(
                    id=str(t.id), name=t.name, description=t.description, category=t.category, creation_method=_METHOD[t.source_type], source_type=t.source_type,
                    module=t.module, status=t.status, updated_at=t.updated_at, updated_by_name=names.get(t.updated_by_user_id) if t.updated_by_user_id else None,
                    is_system=t.is_system, assigned_to=used, has_draft=t.id in drafts, can_delete=can_delete, delete_blocked_reason=blocked,
                    used_by=[AssignmentOut(key=k, name=get_def(k).name if get_def(k) else k) for k in used],
                )
            )
        edited = {o.key: o for o in overrides}
        for d in TEMPLATES:
            studio = by_id.get(by_key.get(d.key)) if d.key in by_key else None
            override = edited.get(d.key)
            if studio is not None and studio.status == TemplateStatus.PUBLISHED.value:
                source = studio.source_type
            else:
                source = "markdown" if override else "default"
            items.append(
                LibraryItem(
                    id=f"system:{d.key}", key=d.key, name=d.name, description=d.description, category=_CATEGORY_OF_KEY.get(d.key, "Custom Emails"),
                    creation_method=_METHOD[source], source_type=source, module=d.category, status="active",
                    updated_at=(studio.updated_at if studio and source == studio.source_type else (override.updated_at if override else None)),
                    updated_by_name=None, is_system=True, assigned_to=[d.key] if source in ("visual", "html", "code") else [],
                    customised=bool(override) or source in ("visual", "html", "code"), has_attachment=d.has_attachment,
                )
            )
        return items

    @staticmethod
    def delete_rule(template: EmailStudioTemplate, used: list[str]) -> tuple[bool, str | None]:
        """Whether a template can be deleted, and if not, why. The same rule backs the screen and the server's refusal."""
        if template.is_system:
            return False, "This is a protected system template and cannot be deleted."
        if used:
            names = ", ".join(get_def(k).name if get_def(k) else k for k in sorted(set(used)))
            return False, f"This template is used for: {names}. Choose another template for it (or switch it back to the built-in wording) under 'Use for', then delete this one."
        return True, None

    async def deleted(self) -> list[LibraryItem]:
        """Templates that were deleted and can still be restored."""
        rows = list(
            (
                await self.db.execute(
                    select(EmailStudioTemplate)
                    .where(EmailStudioTemplate.organization_id == self.organization_id, EmailStudioTemplate.deleted_at.is_not(None))
                    .order_by(EmailStudioTemplate.deleted_at.desc())
                )
            ).scalars().all()
        )
        names = await self._names({t.deleted_by_user_id for t in rows})
        return [
            LibraryItem(
                id=str(t.id), name=t.name, description=t.description, category=t.category, creation_method=_METHOD[t.source_type], source_type=t.source_type,
                module=t.module, status=t.status, updated_at=t.updated_at, is_system=t.is_system, deleted_at=t.deleted_at,
                deleted_by_name=names.get(t.deleted_by_user_id) if t.deleted_by_user_id else None,
            )
            for t in rows
        ]

    # ------------------------------------------------------------------ reading

    def _draft_out(self, v: EmailStudioVersion) -> DraftOut:
        return DraftOut(
            version_id=v.id, version_number=v.version_number, state=v.state, subject=v.subject, preheader=v.preheader, editor_json=v.editor_json,
            html_source=v.html_source, react_source=v.react_source, body_html=v.body_html, code_template_key=v.code_template_key, code_props=v.code_props,
            brand_profile_id=v.brand_profile_id, signature_id=v.signature_id, config=v.config or {}, updated_at=v.updated_at,
        )

    async def out(self, template: EmailStudioTemplate) -> TemplateOut:
        draft = await self._draft(template.id)
        published = await self.db.get(EmailStudioVersion, template.published_version_id) if template.published_version_id else None
        current = draft or published
        if current is None:  # cannot happen: a template always has a draft or a published version
            raise NotFoundError("Email template", template.id)
        for row in {id(r): r for r in (template, draft, published) if r is not None}.values():
            await self.db.refresh(row)  # the database sets updated_at itself; read it back
        assigns = (await self.db.execute(select(EmailTemplateAssignment).where(EmailTemplateAssignment.template_id == template.id))).scalars().all()
        names = await self._names({template.updated_by_user_id})
        return TemplateOut(
            id=template.id, name=template.name, description=template.description, category=template.category, source_type=template.source_type,
            module=template.module, status=template.status, published_version_id=template.published_version_id,
            published_version_number=published.version_number if published else None, has_draft=draft is not None, current=self._draft_out(current),
            assignments=[AssignmentOut(key=a.key, name=get_def(a.key).name if get_def(a.key) else a.key, hackathon_id=a.hackathon_id) for a in assigns],
            updated_at=template.updated_at, updated_by_name=names.get(template.updated_by_user_id) if template.updated_by_user_id else None,
            is_system=template.is_system, deleted_at=template.deleted_at,
        )

    async def versions(self, template: EmailStudioTemplate) -> list[VersionOut]:
        rows = (await self.db.execute(select(EmailStudioVersion).where(EmailStudioVersion.template_id == template.id).order_by(EmailStudioVersion.version_number.desc()))).scalars().all()
        names = await self._names({r.created_by_user_id for r in rows} | {r.published_by_user_id for r in rows})
        return [
            VersionOut(
                id=r.id, version_number=r.version_number, state=r.state, subject=r.subject, created_at=r.created_at, published_at=r.published_at,
                created_by_name=names.get(r.created_by_user_id) if r.created_by_user_id else None,
                published_by_name=names.get(r.published_by_user_id) if r.published_by_user_id else None,
                brand_profile_id=r.brand_profile_id, signature_id=r.signature_id, source_type=template.source_type,
            )
            for r in rows
        ]

    async def version_out(self, template: EmailStudioTemplate, version_id: uuid.UUID) -> DraftOut:
        return self._draft_out(await self._version(template, version_id))

    # ------------------------------------------------------------------ drafts

    async def _own(self, model: type, row_id: uuid.UUID | None):
        if row_id is None:
            return None
        row = await self.db.get(model, row_id)
        if row is None or row.organization_id != self.organization_id:
            raise ValidationError("That brand or signature does not exist.")
        return row

    def _apply(self, version: EmailStudioVersion, source_type: str, payload: DraftPayload) -> None:
        """Copy an editor payload onto a draft, sanitising anything that will be sent."""
        version.subject = payload.subject
        version.preheader = payload.preheader.strip()
        version.brand_profile_id = payload.brand_profile_id
        version.signature_id = payload.signature_id
        version.config = {k: v for k, v in payload.config.items() if k in ("auto_signature", "attachments")}
        if source_type == SourceType.VISUAL.value:
            if payload.editor_json is not None:
                try:
                    version.editor_json = validate_editor_json(payload.editor_json)
                except ValueError as exc:
                    raise ValidationError(str(exc)) from exc
            if payload.html is not None:
                try:
                    version.body_html = sanitize_document(payload.html, payload.subject, payload.preheader)
                except ValueError as exc:
                    raise ValidationError(str(exc)) from exc
        elif source_type == SourceType.HTML.value:
            if payload.html is not None:
                version.html_source = payload.html  # kept exactly as imported; never sent
                try:
                    version.body_html = sanitize_document(payload.html, payload.subject, payload.preheader)
                except ValueError as exc:
                    raise ValidationError(str(exc)) from exc
        elif source_type == SourceType.REACT.value:
            if payload.react_source is not None:
                version.react_source = payload.react_source
            # The browser's HTML is never trusted: the email is always rebuilt here from the source that was saved.
            built = build_react(version.react_source or "", payload.preheader.strip())
            if built.ok:
                version.body_html = built.html
            version.config = {**version.config, "react_build": {"ok": built.ok, "errors": len(built.errors), "warnings": len(built.warnings)}}
        else:
            key = payload.code_template_key or version.code_template_key
            try:
                code = load_code_template(key or "")
            except CodeTemplateError as exc:
                raise ValidationError(str(exc)) from exc
            version.code_template_key = code.key
            if payload.code_props is not None:
                version.code_props = self._clean_props(code, payload.code_props)
            version.body_html = ""  # rendered from the component when used
        version.body_text = html_to_text(version.body_html) if version.body_html else ""

    @staticmethod
    def _clean_props(code, props: dict[str, str]) -> dict[str, str]:
        import re

        out: dict[str, str] = {}
        defs = {p.name: p for p in code.props}
        for name, value in props.items():
            if name not in defs:
                continue
            text = str(value)
            if len(text) > 2000 or re.search(r"[\x00]", text):
                raise ValidationError(f"'{defs[name].label}' is too long or contains invalid characters.")
            if defs[name].type == "color" and text and not re.match(r"^#[0-9a-fA-F]{6}$", text):
                raise ValidationError(f"'{defs[name].label}' must be a colour like #2563eb.")
            if defs[name].type == "url" and text and not re.match(r"^(https?://|mailto:|\{\{)", text):
                raise ValidationError(f"'{defs[name].label}' must be a web address or a placeholder.")
            if defs[name].type != "textarea" and re.search(r"[\r\n]", text):
                raise ValidationError(f"'{defs[name].label}' must be on one line.")
            out[name] = text
        return out

    async def create(self, payload: CreatePayload, user_id: uuid.UUID) -> TemplateOut:
        if payload.source_type == "code" and not payload.code_template_key:
            raise ValidationError("Choose an approved React Email template.")
        if payload.source_type == "react" and not (payload.react_source or "").strip():
            raise ValidationError("Paste the React Email code to import.")
        template = EmailStudioTemplate(
            organization_id=self.organization_id, name=payload.name.strip(), description=(payload.description or "").strip(), category=payload.category,
            source_type=payload.source_type, module=payload.module, status=TemplateStatus.DRAFT.value, created_by_user_id=user_id, updated_by_user_id=user_id,
        )
        self.db.add(template)
        await self.db.flush()
        version = EmailStudioVersion(
            organization_id=self.organization_id, template_id=template.id, version_number=1, state=VersionState.DRAFT.value, created_by_user_id=user_id,
        )
        await self._own(EmailBrandProfile, payload.brand_profile_id)
        await self._own(EmailSignature, payload.signature_id)
        self._apply(version, payload.source_type, payload)
        if payload.source_type == "code" and not payload.subject:
            version.subject = load_code_template(payload.code_template_key or "").subject
        self.db.add(version)
        await self.db.flush()
        return await self.out(template)

    async def save_draft(self, template: EmailStudioTemplate, payload: DraftPayload, user_id: uuid.UUID) -> TemplateOut:
        if template.status == TemplateStatus.ARCHIVED.value:
            raise ConflictError("This template is archived. Restore it before editing.")
        await self._own(EmailBrandProfile, payload.brand_profile_id)
        await self._own(EmailSignature, payload.signature_id)
        draft = await self._draft(template.id)
        if draft is None:  # first edit of a published template: start a draft from it
            published = await self.db.get(EmailStudioVersion, template.published_version_id) if template.published_version_id else None
            draft = EmailStudioVersion(
                organization_id=self.organization_id, template_id=template.id, version_number=await self._next_number(template.id), state=VersionState.DRAFT.value,
                created_by_user_id=user_id,
            )
            if published is not None:
                self._copy(published, draft)
            self.db.add(draft)
        self._apply(draft, template.source_type, payload)
        for field in ("name", "description", "category", "module"):
            value = getattr(payload, field)
            if value is not None:
                setattr(template, field, value.strip() if isinstance(value, str) else value)
        template.updated_by_user_id = user_id
        await self.db.flush()
        return await self.out(template)

    @staticmethod
    def _copy(source: EmailStudioVersion, target: EmailStudioVersion) -> None:
        for field in ("subject", "preheader", "editor_json", "html_source", "react_source", "body_html", "body_text", "code_template_key", "code_props", "brand_profile_id", "signature_id", "config"):
            setattr(target, field, getattr(source, field))

    async def discard_draft(self, template: EmailStudioTemplate) -> TemplateOut:
        draft = await self._draft(template.id)
        if draft is None:
            return await self.out(template)
        if template.published_version_id is None:
            raise ConflictError("This template has no published version, so its draft cannot be discarded. Archive it instead.")
        await self.db.delete(draft)
        await self.db.flush()
        return await self.out(template)

    # ------------------------------------------------------------------ publishing

    async def _html_of(self, version: EmailStudioVersion, source_type: str) -> str:
        if source_type == "code":
            code = load_code_template(version.code_template_key or "")
            return fill_props(code.html, {**code.default_props(), **(version.code_props or {})})
        return version.body_html

    async def problems(self, template: EmailStudioTemplate, version: EmailStudioVersion) -> list[str]:
        """Why this version cannot be published (or used for the emails it is assigned to)."""
        found: list[str] = []
        if not version.subject.strip():
            found.append("The subject cannot be empty.")
        if template.source_type == SourceType.REACT.value:
            built = build_react(version.react_source or "", version.preheader)
            if not built.ok:
                first = built.errors[0]
                where = f"line {first.line}: " if first.line else ""
                return found + [f"The React Email code has {len(built.errors)} error(s) and cannot be published. First: {where}{first.message}"]
        try:
            html = await self._html_of(version, template.source_type)
        except CodeTemplateError as exc:
            return [str(exc)]
        if not html.strip():
            found.append("The email has no content.")
        found += component_misuse(html)
        used = [n for n in placeholders_in(html, version.subject) if n not in COMPONENT_NAMES]
        assigns = (await self.db.execute(select(EmailTemplateAssignment).where(EmailTemplateAssignment.template_id == template.id))).scalars().all()
        for a in assigns:
            definition = get_def(a.key)
            if definition is None:
                continue
            bad = unsupported(used, allowed_for_key(definition) or set())
            if bad:
                found.append(f"{definition.name} cannot use: " + ", ".join("{{" + n + "}}" for n in bad) + ".")
            for name in definition.required:
                if name not in used:
                    found.append(f"{definition.name} must keep {{{{{name}}}}}, otherwise the person has nothing to click.")
        return found

    async def publish(self, template: EmailStudioTemplate, user_id: uuid.UUID) -> TemplateOut:
        if template.status == TemplateStatus.ARCHIVED.value:
            raise ConflictError("This template is archived.")
        draft = await self._draft(template.id)
        if draft is None:
            raise ConflictError("There is nothing new to publish.")
        found = await self.problems(template, draft)
        if found:
            raise ValidationError(" ".join(found))
        previous = await self.db.get(EmailStudioVersion, template.published_version_id) if template.published_version_id else None
        if previous is not None:
            previous.state = VersionState.SUPERSEDED.value
            await self.db.flush()
        draft.state = VersionState.PUBLISHED.value
        draft.published_by_user_id = user_id
        draft.published_at = datetime.now(timezone.utc)
        template.published_version_id = draft.id
        template.status = TemplateStatus.PUBLISHED.value
        template.updated_by_user_id = user_id
        await self.db.flush()
        return await self.out(template)

    async def restore(self, template: EmailStudioTemplate, version_id: uuid.UUID, user_id: uuid.UUID) -> TemplateOut:
        """Make an earlier version the draft. It is not used until published again."""
        source = await self._version(template, version_id)
        draft = await self._draft(template.id)
        if draft is None:
            draft = EmailStudioVersion(
                organization_id=self.organization_id, template_id=template.id, version_number=await self._next_number(template.id), state=VersionState.DRAFT.value,
                created_by_user_id=user_id,
            )
            self.db.add(draft)
        self._copy(source, draft)
        template.updated_by_user_id = user_id
        await self.db.flush()
        return await self.out(template)

    async def duplicate(self, template: EmailStudioTemplate, user_id: uuid.UUID) -> TemplateOut:
        current = await self._draft(template.id) or (await self.db.get(EmailStudioVersion, template.published_version_id) if template.published_version_id else None)
        copy = EmailStudioTemplate(
            organization_id=self.organization_id, name=f"{template.name} (copy)"[:200], description=template.description, category=template.category,
            source_type=template.source_type, module=template.module, status=TemplateStatus.DRAFT.value, created_by_user_id=user_id, updated_by_user_id=user_id,
        )
        self.db.add(copy)
        await self.db.flush()
        version = EmailStudioVersion(organization_id=self.organization_id, template_id=copy.id, version_number=1, state=VersionState.DRAFT.value, created_by_user_id=user_id)
        if current is not None:
            self._copy(current, version)
        self.db.add(version)
        await self.db.flush()
        return await self.out(copy)

    async def archive(self, template: EmailStudioTemplate, archive: bool, user_id: uuid.UUID) -> TemplateOut:
        if archive:
            used = (await self.db.execute(select(func.count()).select_from(EmailTemplateAssignment).where(EmailTemplateAssignment.template_id == template.id))).scalar_one()
            if used:
                raise ConflictError("This template is in use by an ERPX email. Assign another template (or switch back to the built-in wording) first.")
            template.status = TemplateStatus.ARCHIVED.value
        else:
            template.status = TemplateStatus.PUBLISHED.value if template.published_version_id else TemplateStatus.DRAFT.value
        template.updated_by_user_id = user_id
        await self.db.flush()
        return await self.out(template)

    async def delete(self, template: EmailStudioTemplate, user_id: uuid.UUID) -> None:
        """Delete (hide) a template you made. A protected system template can never be deleted, and neither can one an ERPX email
        is using until that email is pointed elsewhere (otherwise it would silently fall back to older wording). Nothing is removed:
        the versions, the history of emails already sent and the audit trail stay, and the template can be restored."""
        used = list(
            (await self.db.execute(select(EmailTemplateAssignment.key).where(EmailTemplateAssignment.template_id == template.id))).scalars().all()
        )
        allowed, reason = self.delete_rule(template, used)
        if not allowed:
            if template.is_system:
                raise AuthorizationError(reason or "This template cannot be deleted.")
            raise ConflictError(reason or "This template cannot be deleted.")
        template.deleted_at = datetime.now(timezone.utc)
        template.deleted_by_user_id = user_id
        template.updated_by_user_id = user_id
        await self.db.flush()

    async def restore_deleted(self, template_id: uuid.UUID, user_id: uuid.UUID) -> TemplateOut:
        template = await self.template(template_id, include_deleted=True)
        if template.deleted_at is None:
            raise ConflictError("This template has not been deleted.")
        template.deleted_at = None
        template.deleted_by_user_id = None
        template.updated_by_user_id = user_id
        await self.db.flush()
        return await self.out(template)

    # ------------------------------------------------------------------ which template an ERPX email uses

    async def assign(self, key: str, template_id: uuid.UUID, hackathon_id: uuid.UUID | None, user_id: uuid.UUID) -> None:
        definition = get_def(key)
        if definition is None or (hackathon_id is not None and not definition.event_scoped):
            raise NotFoundError("Email", key)
        template = await self.template(template_id)
        if template.status != TemplateStatus.PUBLISHED.value or template.published_version_id is None:
            raise ValidationError("Publish the template before using it for an ERPX email.")
        version = await self.db.get(EmailStudioVersion, template.published_version_id)
        assert version is not None
        used = [n for n in placeholders_in(await self._html_of(version, template.source_type), version.subject) if n not in COMPONENT_NAMES]
        found: list[str] = []
        bad = unsupported(used, allowed_for_key(definition) or set())
        if bad:
            found.append("This email cannot use: " + ", ".join("{{" + n + "}}" for n in bad) + ".")
        for name in definition.required:
            if name not in used:
                found.append("The template must keep {{" + name + "}}, otherwise the person has nothing to click.")
        if found:
            raise ValidationError(" ".join(found))
        query = select(EmailTemplateAssignment).where(EmailTemplateAssignment.organization_id == self.organization_id, EmailTemplateAssignment.key == key)
        query = query.where(EmailTemplateAssignment.hackathon_id == hackathon_id if hackathon_id else EmailTemplateAssignment.hackathon_id.is_(None))
        row = (await self.db.execute(query)).scalar_one_or_none()
        if row is None:
            self.db.add(EmailTemplateAssignment(organization_id=self.organization_id, key=key, hackathon_id=hackathon_id, template_id=template.id, assigned_by_user_id=user_id))
        else:
            row.template_id, row.assigned_by_user_id = template.id, user_id
        await self.db.flush()

    async def unassign(self, key: str, hackathon_id: uuid.UUID | None) -> None:
        query = select(EmailTemplateAssignment).where(EmailTemplateAssignment.organization_id == self.organization_id, EmailTemplateAssignment.key == key)
        query = query.where(EmailTemplateAssignment.hackathon_id == hackathon_id if hackathon_id else EmailTemplateAssignment.hackathon_id.is_(None))
        row = (await self.db.execute(query)).scalar_one_or_none()
        if row is not None:
            await self.db.delete(row)
            await self.db.flush()

    # ------------------------------------------------------------------ previews and tests

    async def values_for(self, context: PreviewContext) -> tuple[dict[str, object], str | None]:
        """The values to preview with (sample data, or a real selected student of an internship) and the ERPX email they stand for."""
        key = context.key if context.key and get_def(context.key) else None
        values: dict[str, object] = dict(sample_for(key))
        if context.type == "internship" and context.internship_id and context.student_id:
            values.update(await self._internship_values(context.internship_id, context.student_id))
        return values, key

    async def _internship_values(self, internship_id: uuid.UUID, student_id: uuid.UUID) -> dict[str, object]:
        from modules.our_internships.letter_pdf import letter_values
        from modules.our_internships.letters import LetterService, facts_of, letter_date_text
        from modules.our_internships.service import OurInternshipService

        internship = await OurInternshipService(self.db).get(internship_id, self.organization_id)
        service = LetterService(self.db)
        loaded = await service.load(internship)
        rows = await service.selected(internship, [student_id])
        if not rows:
            raise NotFoundError("Selected student", student_id)
        selection, student, institution = rows[0]
        facts = facts_of(student, institution)
        values: dict[str, object] = dict(letter_values(loaded.config, facts, internship.title, selection.offer_reference or "OFR-PREVIEW", letter_date_text(loaded.config)))
        values.update(full_name=facts.name, internship_title=internship.title, course_title=internship.title, login_url=values.get("login_url", ""))
        return values

    def _draft_from(self, request_draft: DraftPayload, source_type: str) -> Draft:
        body = ""
        if source_type in ("visual", "html") and request_draft.html:
            body = sanitize_document(request_draft.html, request_draft.subject, request_draft.preheader)
        elif source_type == "react":
            built = build_react(request_draft.react_source or "", request_draft.preheader.strip())
            if not built.ok:
                first = built.errors[0]
                raise ValueError(f"The React Email code has errors. {'Line ' + str(first.line) + ': ' if first.line else ''}{first.message}")
            body = built.html
        return Draft(
            source_type=source_type, subject=request_draft.subject, preheader=request_draft.preheader, body_html=body,
            code_template_key=request_draft.code_template_key, code_props=self._clean_props(load_code_template(request_draft.code_template_key or ""), request_draft.code_props or {}) if source_type == "code" else None,
            brand_profile_id=request_draft.brand_profile_id, signature_id=request_draft.signature_id, config=request_draft.config,
        )

    async def preview(self, source_type: str, draft_payload: DraftPayload, context: PreviewContext) -> PreviewResponse:
        values, key = await self.values_for(context)
        try:
            draft = self._draft_from(draft_payload, source_type)
            definition = get_def(key) if key else None
            rendered = await render_draft(self.db, self.organization_id, draft, values, allowed=allowed_for_key(definition), strict=False)
        except (ValueError, CodeTemplateError) as exc:
            raise ValidationError(str(exc)) from exc
        used = [n for n in placeholders_in(draft.body_html or (load_code_template(draft.code_template_key or "").html if source_type == "code" else ""), draft.subject) if n not in COMPONENT_NAMES]
        bad = unsupported(used, allowed_for_key(get_def(key)) if key else {r.name for r in catalog()})
        attachments = [a for a in (draft.config.get("attachments") or []) if isinstance(a, dict)]
        return PreviewResponse(subject=rendered.subject, html=rendered.html, text=rendered.text, missing=rendered.missing, warnings=rendered.warnings, unsupported=bad, attachments=attachments)

    def react_build(self, source: str, preheader: str = "") -> ReactBuildResponse:
        """Read pasted React Email code and report what it makes -- or exactly what stops it. Nothing is executed or stored."""
        built = build_react(source, preheader.strip())

        def issue(i):
            return ReactIssue(severity=i.severity, message=i.message, line=i.line, column=i.column, code=i.code)

        allowed = {r.name for r in catalog()}
        return ReactBuildResponse(
            ok=built.ok, errors=[issue(i) for i in built.errors], warnings=[issue(i) for i in built.warnings], html=built.html, text=built.text, title=built.title,
            preheader=built.preheader, placeholders=built.placeholders, unsupported_placeholders=unsupported(built.placeholders, allowed), components=built.components,
        )

    async def send_test(self, source_type: str, draft_payload: DraftPayload, context: PreviewContext, to_email: str, user_id: uuid.UUID, template_id: uuid.UUID | None) -> tuple[bool, str]:
        """Send the email being edited, with sample (or chosen) data, to one address. It is marked as a test, uses safe sample links and
        starts no ERPX workflow."""
        now = time.monotonic()
        recent = _recent_tests[user_id]
        while recent and now - recent[0] > 3600:
            recent.popleft()
        if len(recent) >= TEST_SENDS_PER_HOUR:
            raise RateLimitError(f"You can send {TEST_SENDS_PER_HOUR} test emails an hour. Try again later.")
        preview = await self.preview(source_type, draft_payload, context)
        if preview.unsupported:
            raise ValidationError("Remove the unsupported placeholders first: " + ", ".join("{{" + n + "}}" for n in preview.unsupported))
        recent.append(now)
        note = "This is a test email: the details are sample values, the links go nowhere real, and no one else received it."
        html = preview.html
        banner = f'<div style="background:#fef3c7;color:#92400e;font:12px Arial,sans-serif;padding:8px 12px;text-align:center">{note}</div>'
        index = html.find("<body")
        if index != -1:
            close = html.find(">", index)
            html = html[: close + 1] + banner + html[close + 1 :]
        set_send_meta(SendMeta(organization_id=self.organization_id, key=context.key, template_id=template_id, source=source_type, is_test=True, sent_by_user_id=user_id))
        sent = await email_service.send(to_email, f"[TEST] {preview.subject}", f"{preview.text}\n\n--\n{note}", html)
        if sent:
            return True, f"Sent to {to_email}. Check that inbox (and the spam folder)."
        return False, "The mail server did not accept the message, so nothing was sent. Check the SMTP settings on the server."

    # ------------------------------------------------------------------ rendering for real use (also used by other modules)

    async def render_published(self, key: str, values: dict[str, object], hackathon_id: uuid.UUID | None = None):
        from modules.email_studio.engine import render_assigned

        definition = get_def(key)
        return await render_assigned(
            self.db, self.organization_id, key, values, hackathon_id, allowed=allowed_for_key(definition), required=definition.required if definition else (),
        )


__all__ = ["StudioService", "MissingPlaceholders", "CATEGORIES", "catalog", "sample_for", "code_templates_out"]
