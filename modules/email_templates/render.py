"""
Turn a template key and its values into the (subject, text, html) of an email, using the organisation's
(or hackathon's) edited wording when there is one and the built-in default otherwise.

Sending an email must never fail because of a template: any problem looking up or rendering an edit falls
back to the default wording.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.email_templates.models import EmailTemplate
from modules.users.models import UserProfile
from modules.authentication.models import User
from packages.email.history import SendMeta, set_send_meta
from packages.email.markup import render_body, render_subject
from packages.email.registry import TemplateDef, get_def

logger = get_logger(__name__)


def render_with(definition: TemplateDef, subject: str, body: str, values: dict[str, object]) -> tuple[str, str, str]:
    """(subject, plain text, html) for this wording."""
    html, text = render_body(body, values, definition.button_color)
    return render_subject(subject, values), text, html


def render_default(key: str, values: dict[str, object]) -> tuple[str, str, str]:
    definition = get_def(key)
    if definition is None:
        raise KeyError(f"Unknown email template: {key}")
    return render_with(definition, definition.subject, definition.body, values)


async def find_override(
    db: AsyncSession, organization_id: uuid.UUID, key: str, hackathon_id: uuid.UUID | None = None
) -> EmailTemplate | None:
    """The hackathon's own wording if it has one, otherwise the organisation's."""
    if hackathon_id is not None:
        row = (
            await db.execute(
                select(EmailTemplate).where(
                    EmailTemplate.organization_id == organization_id,
                    EmailTemplate.key == key,
                    EmailTemplate.hackathon_id == hackathon_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            return row
    return (
        await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.organization_id == organization_id,
                EmailTemplate.key == key,
                EmailTemplate.hackathon_id.is_(None),
            )
        )
    ).scalar_one_or_none()


async def organization_for_email(db: AsyncSession, email: str) -> uuid.UUID | None:
    """Which organisation a recipient belongs to (for emails sent without one in hand)."""
    return (
        await db.execute(
            select(UserProfile.organization_id)
            .join(User, User.id == UserProfile.user_id)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
        )
    ).scalar_one_or_none()


async def render_email_full(
    db: AsyncSession,
    key: str,
    values: dict[str, object],
    organization_id: uuid.UUID | None = None,
    hackathon_id: uuid.UUID | None = None,
    recipient_email: str | None = None,
) -> tuple[str, str, str, SendMeta]:
    """(subject, text, html, note about which template made it)."""
    definition = get_def(key)
    if definition is None:
        raise KeyError(f"Unknown email template: {key}")
    try:
        if organization_id is None and recipient_email:
            organization_id = await organization_for_email(db, recipient_email)
        if organization_id is not None:
            # 1. a published Email Studio template that an administrator assigned to this email
            try:
                from modules.email_studio.engine import render_assigned

                studio = await render_assigned(
                    db, organization_id, key, values, hackathon_id,
                    allowed={v.name for v in definition.variables}, required=definition.required,
                )
            except Exception:  # noqa: BLE001 - a studio template that cannot be filled in must not stop the email
                logger.exception("email_studio_render_failed", key=key)
                studio = None
            if studio is not None:
                note = SendMeta(
                    organization_id=organization_id, key=key, module=definition.category, template_id=studio.template_id,
                    version_id=studio.version_id, source=studio.source, reply_to=studio.reply_to, from_name=studio.from_name,
                    extra_attachments=studio.attachments, requires=studio.requires,
                )
                return studio.subject, studio.text, studio.html, note
            # 2. the wording edited in the older Markdown editor
            override = await find_override(db, organization_id, key, hackathon_id)
            if override is not None:
                note = SendMeta(organization_id=organization_id, key=key, module=definition.category, source="markdown")
                return (*render_with(definition, override.subject, override.body, values), note)
    except Exception:  # noqa: BLE001 - never block an email over its template
        logger.exception("email_template_lookup_failed", key=key)
    # 3. the built-in wording
    note = SendMeta(organization_id=organization_id, key=key, module=definition.category, source="default")
    return (*render_with(definition, definition.subject, definition.body, values), note)


async def render_email(
    db: AsyncSession,
    key: str,
    values: dict[str, object],
    organization_id: uuid.UUID | None = None,
    hackathon_id: uuid.UUID | None = None,
    recipient_email: str | None = None,
) -> tuple[str, str, str]:
    subject, text, html, note = await render_email_full(db, key, values, organization_id, hackathon_id, recipient_email)
    set_send_meta(note)  # picked up by EmailService.send in the same task
    return subject, text, html


async def _render_in_new_session(
    key: str,
    values: dict[str, object],
    organization_id: uuid.UUID | None,
    hackathon_id: uuid.UUID | None,
    recipient_email: str | None,
) -> tuple[str, str, str, SendMeta]:
    async with get_db_context() as db:
        return await render_email_full(db, key, values, organization_id, hackathon_id, recipient_email)


def render_email_sync(
    key: str,
    values: dict[str, object],
    organization_id: uuid.UUID | str | None = None,
    hackathon_id: uuid.UUID | str | None = None,
    recipient_email: str | None = None,
) -> tuple[str, str, str]:
    """For Celery tasks (which are synchronous): same as `render_email`, in its own database session."""
    try:
        subject, text, html, note = run_async(
            _render_in_new_session(
                key,
                values,
                uuid.UUID(str(organization_id)) if organization_id else None,
                uuid.UUID(str(hackathon_id)) if hackathon_id else None,
                recipient_email,
            )
        )
        set_send_meta(note)
        return subject, text, html
    except Exception:  # noqa: BLE001 - never block an email over its template
        logger.exception("email_template_render_failed", key=key)
        return render_default(key, values)
