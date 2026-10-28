"""
Turning a studio template version into the (subject, text, html) of an email.

The same function serves previews, test sends and the real automated emails, so what an administrator previews is what is
sent. Nothing here sends anything.
"""

import html as html_lib
import uuid
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import undefer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from modules.email_studio.code_templates import CodeTemplateError, load_code_template
from modules.email_studio.models import (
    EmailAsset,
    EmailBrandProfile,
    EmailSignature,
    EmailStudioTemplate,
    EmailStudioVersion,
    EmailTemplateAssignment,
    TemplateStatus,
)
from modules.email_studio.placeholders import (
    BRAND_NAMES,
    COMPONENT_NAMES,
    component_misuse,
    fill_html,
    fill_props,
    fill_subject,
    missing,
    placeholders_in,
    unsupported,
)
from modules.email_studio.sanitize import html_to_text


class MissingPlaceholders(ValueError):
    """The email uses placeholders that have no value, so it must not be sent as it is."""

    def __init__(self, names: list[str]):
        self.names = names
        super().__init__("Missing values: " + ", ".join("{{" + n + "}}" for n in names))


@dataclass
class Rendered:
    subject: str
    text: str
    html: str
    template_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    source: str | None = None
    reply_to: str = ""
    from_name: str = ""
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    attachments: list[Any] = field(default_factory=list)  # shared files that go with every copy
    requires: list[str] = field(default_factory=list)  # recipient documents that must be supplied by the sender


def asset_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/public/email-assets/{token}"


async def asset_tokens(db: AsyncSession, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = [i for i in ids if i]
    if not wanted:
        return {}
    rows = (await db.execute(select(EmailAsset.id, EmailAsset.token).where(EmailAsset.id.in_(wanted)))).all()
    return {i: t for i, t in rows}


def _e(text: str) -> str:
    return html_lib.escape(text or "")


def _link(url: str, label: str, color: str) -> str:
    return f'<a href="{html_lib.escape(url, quote=True)}" style="color:{color};text-decoration:none">{_e(label)}</a>'


def header_html(brand: EmailBrandProfile | None, tokens: dict[uuid.UUID, str]) -> str:
    if brand is None:
        return ""
    logo = tokens.get(brand.logo_asset_id) if brand.logo_asset_id else None
    image = f'<img src="{asset_url(logo)}" alt="{_e(brand.company_name or brand.name)}" height="40" style="display:block;margin:0 auto 8px;height:40px;border:0" />' if logo else ""
    name = f'<div style="font-size:20px;font-weight:700;color:{brand.primary_color}">{_e(brand.company_name or brand.name)}</div>' if (brand.company_name or brand.name) else ""
    tagline = f'<div style="font-size:13px;color:{brand.text_color};opacity:.7">{_e(brand.tagline)}</div>' if brand.tagline else ""
    return (
        f'<table width="100%" role="presentation" cellpadding="0" cellspacing="0" style="background-color:{brand.background_color}">'
        f'<tr><td align="center" style="padding:20px 16px;border-bottom:3px solid {brand.primary_color}">{image}{name}{tagline}</td></tr></table>'
    )


def footer_html(brand: EmailBrandProfile | None) -> str:
    if brand is None:
        return ""
    lines = [brand.company_name or brand.name]
    if brand.address:
        lines.append(brand.address)
    contact = " | ".join(x for x in (brand.contact_email, brand.phone) if x)
    if contact:
        lines.append(contact)
    rows = "".join(f'<div style="margin:2px 0">{_e(line)}</div>' for line in lines if line)
    links = []
    if brand.website:
        links.append(_link(brand.website, brand.website, brand.primary_color))
    for item in brand.social_links or []:
        if isinstance(item, dict) and item.get("url") and item.get("label"):
            links.append(_link(str(item["url"]), str(item["label"]), brand.primary_color))
    link_row = f'<div style="margin:6px 0">{" &nbsp;|&nbsp; ".join(links)}</div>' if links else ""
    year = datetime.now(timezone.utc).year
    return (
        f'<table width="100%" role="presentation" cellpadding="0" cellspacing="0" style="background-color:{brand.background_color}">'
        f'<tr><td align="center" style="padding:20px 16px;font-size:12px;color:{brand.text_color};opacity:.85">{rows}{link_row}'
        f'<div style="margin-top:6px">&copy; {year} {_e(brand.company_name or brand.name)}</div></td></tr></table>'
    )


def signature_html(sig: EmailSignature | None, tokens: dict[uuid.UUID, str]) -> str:
    if sig is None:
        return ""
    style = sig.style or {}
    color = style.get("color") if isinstance(style.get("color"), str) else "#111827"
    size = style.get("font_size") if isinstance(style.get("font_size"), int) else 14
    parts: list[str] = []
    if sig.signature_asset_id and tokens.get(sig.signature_asset_id) and sig.signature_approved_at:
        parts.append(f'<img src="{asset_url(tokens[sig.signature_asset_id])}" alt="Signature" height="48" style="display:block;height:48px;border:0;margin:4px 0" />')
    if sig.person_name:
        parts.append(f'<div style="font-weight:700">{_e(sig.person_name)}</div>')
    for value in (sig.designation, sig.company_name):
        if value:
            parts.append(f"<div>{_e(value)}</div>")
    contact = " | ".join(x for x in (sig.email, sig.phone) if x)
    if contact:
        parts.append(f"<div>{_e(contact)}</div>")
    if sig.website:
        parts.append(f"<div>{_link(sig.website, sig.website, color)}</div>")
    if sig.logo_asset_id and tokens.get(sig.logo_asset_id):
        parts.append(f'<img src="{asset_url(tokens[sig.logo_asset_id])}" alt="{_e(sig.company_name)}" height="32" style="display:block;height:32px;border:0;margin-top:8px" />')
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:16px"><tr>'
        f'<td style="font-size:{size}px;line-height:1.5;color:{color};text-align:{style.get("align", "left") if style.get("align") in ("left", "center", "right") else "left"}">'
        + "".join(parts)
        + "</td></tr></table>"
    )


def brand_values(brand: EmailBrandProfile | None, sig: EmailSignature | None, tokens: dict[uuid.UUID, str]) -> dict[str, object]:
    """Values the brand and signature supply for placeholders (a sender's own value for the same name wins)."""
    values: dict[str, object] = {"current_year": str(datetime.now(timezone.utc).year)}
    if brand is not None:
        values.update(
            company_name=brand.company_name or brand.name, brand_name=brand.name, company_website=brand.website,
            company_email=brand.contact_email, company_phone=brand.phone, company_address=brand.address,
            logo_url=asset_url(tokens[brand.logo_asset_id]) if brand.logo_asset_id and tokens.get(brand.logo_asset_id) else "",
        )
    if sig is not None:
        values.update(authorized_signatory=sig.person_name, authorized_designation=sig.designation)
        values.setdefault("company_name", sig.company_name)
    return values


async def default_brand(db: AsyncSession, organization_id: uuid.UUID) -> EmailBrandProfile | None:
    return (
        await db.execute(select(EmailBrandProfile).where(EmailBrandProfile.organization_id == organization_id, EmailBrandProfile.is_default.is_(True)))
    ).scalar_one_or_none()


@dataclass
class Draft:
    """What can be rendered: a stored version, or the unsaved state of the editor (for previews)."""

    source_type: str
    subject: str
    preheader: str
    body_html: str
    code_template_key: str | None = None
    code_props: dict | None = None
    brand_profile_id: uuid.UUID | None = None
    signature_id: uuid.UUID | None = None
    config: dict = field(default_factory=dict)
    template_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None


def draft_of(version: EmailStudioVersion, source_type: str) -> Draft:
    return Draft(
        source_type=source_type, subject=version.subject, preheader=version.preheader, body_html=version.body_html,
        code_template_key=version.code_template_key, code_props=version.code_props, brand_profile_id=version.brand_profile_id,
        signature_id=version.signature_id, config=version.config or {}, template_id=version.template_id, version_id=version.id,
    )


async def _attachments(db: AsyncSession, organization_id: uuid.UUID, config: object) -> tuple[list[Any], list[str]]:
    """The shared PDFs a template attaches to every copy, and the names of the recipient documents it requires."""
    from packages.email.service import EmailAttachment

    shared: list[Any] = []
    requires: list[str] = []
    for item in config if isinstance(config, list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "recipient" and item.get("required"):
            requires.append(str(item.get("name") or "document"))
        elif item.get("kind") == "shared" and item.get("asset"):
            try:
                asset_id = uuid.UUID(str(item["asset"]))
            except ValueError:
                continue
            row = (
                await db.execute(select(EmailAsset).options(undefer(EmailAsset.data)).where(EmailAsset.id == asset_id, EmailAsset.organization_id == organization_id))
            ).scalar_one_or_none()
            if row is not None and row.content_type == "application/pdf":
                name = row.filename if row.filename.lower().endswith(".pdf") else row.filename + ".pdf"
                shared.append(EmailAttachment(filename=name, content=row.data, mime_type="application/pdf"))
    return shared, requires


def _inject_before_body_end(html: str, block: str) -> str:
    index = html.lower().rfind("</body>")
    return html[:index] + block + html[index:] if index != -1 else html + block


async def render_draft(
    db: AsyncSession,
    organization_id: uuid.UUID,
    draft: Draft,
    values: dict[str, object],
    *,
    allowed: set[str] | None = None,
    required: tuple[str, ...] = (),
    strict: bool = True,
) -> Rendered:
    """Render a draft with values. With ``strict`` a placeholder that has no value raises MissingPlaceholders; without it
    the result lists them in ``missing`` (for previews)."""
    brand = await db.get(EmailBrandProfile, draft.brand_profile_id) if draft.brand_profile_id else await default_brand(db, organization_id)
    if brand is not None and brand.organization_id != organization_id:
        brand = None
    sig = await db.get(EmailSignature, draft.signature_id) if draft.signature_id else None
    if sig is not None and sig.organization_id != organization_id:
        sig = None
    tokens = await asset_tokens(db, [brand.logo_asset_id if brand else None, sig.logo_asset_id if sig else None, sig.signature_asset_id if sig else None])

    html = draft.body_html
    if draft.source_type == "code":
        try:
            code = load_code_template(draft.code_template_key or "")
        except CodeTemplateError as exc:
            raise ValueError(str(exc)) from exc
        props = {**code.default_props(), **{k: v for k, v in (draft.code_props or {}).items() if k in code.prop_names}}
        if brand is not None:  # brand colours and name fill the properties the template declares for them
            for name, value in (("primary_color", brand.primary_color), ("secondary_color", brand.secondary_color), ("accent_color", brand.accent_color),
                                ("background_color", brand.background_color), ("text_color", brand.text_color), ("company_name", brand.company_name or brand.name)):
                if name in code.prop_names and not (draft.code_props or {}).get(name):
                    props[name] = value
        html = fill_props(code.html, props)

    blocks: dict[str, str] = {}
    names_in_body = placeholders_in(html)
    if "signature" in names_in_body:
        blocks["signature"] = signature_html(sig, tokens)
    elif sig is not None and draft.config.get("auto_signature", draft.source_type == "visual"):
        html = _inject_before_body_end(html, signature_html(sig, tokens))
    if "brand_header" in names_in_body:
        blocks["brand_header"] = header_html(brand, tokens)
    if "brand_footer" in names_in_body:
        blocks["brand_footer"] = footer_html(brand)

    merged = {**brand_values(brand, sig, tokens), **{k: v for k, v in values.items() if v is not None}}
    used = [n for n in placeholders_in(html, draft.subject) if n not in COMPONENT_NAMES]
    gone = missing(used, merged, required)
    problems = component_misuse(html)
    if allowed is not None:
        bad = unsupported(used, allowed | set(BRAND_NAMES))
        if bad:
            problems.append("Unsupported placeholders: " + ", ".join("{{" + n + "}}" for n in bad))
    if gone and strict:
        raise MissingPlaceholders(gone)

    final = fill_html(html, merged, blocks)
    shared, requires = await _attachments(db, organization_id, draft.config.get("attachments"))
    return Rendered(
        subject=fill_subject(draft.subject, merged),
        text=html_to_text(final),
        html=final,
        template_id=draft.template_id,
        version_id=draft.version_id,
        source=draft.source_type,
        reply_to=brand.reply_to if brand else "",
        from_name=brand.from_name if brand else "",
        missing=gone,
        warnings=problems,
        attachments=shared,
        requires=requires,
    )


# ------------------------------------------------------------------ which template an ERPX email uses


async def assigned_version(
    db: AsyncSession, organization_id: uuid.UUID, key: str, hackathon_id: uuid.UUID | None = None
) -> tuple[EmailStudioTemplate, EmailStudioVersion] | None:
    """The published studio version an ERPX email is set to use (the hackathon's own, else the organisation's), if any."""
    for scope in ([hackathon_id] if hackathon_id else []) + [None]:
        query = select(EmailTemplateAssignment).where(EmailTemplateAssignment.organization_id == organization_id, EmailTemplateAssignment.key == key)
        query = query.where(EmailTemplateAssignment.hackathon_id == scope if scope else EmailTemplateAssignment.hackathon_id.is_(None))
        row = (await db.execute(query)).scalar_one_or_none()
        if row is None:
            continue
        template = await db.get(EmailStudioTemplate, row.template_id)
        if template is None or template.status != TemplateStatus.PUBLISHED.value or template.published_version_id is None:
            continue
        version = await db.get(EmailStudioVersion, template.published_version_id)
        if version is not None:
            return template, version
    return None


async def render_assigned(
    db: AsyncSession, organization_id: uuid.UUID, key: str, values: dict[str, object], hackathon_id: uuid.UUID | None = None,
    allowed: set[str] | None = None, required: tuple[str, ...] = (),
) -> Rendered | None:
    found = await assigned_version(db, organization_id, key, hackathon_id)
    if found is None:
        return None
    template, version = found
    return await render_draft(db, organization_id, draft_of(version, template.source_type), values, allowed=allowed, required=required, strict=True)
