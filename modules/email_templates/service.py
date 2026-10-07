import time
import uuid
from collections import defaultdict, deque

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, RateLimitError, ValidationError
from app.core.logging_config import get_logger
from modules.authentication.models import User
from modules.email_templates.models import EmailTemplate
from modules.email_templates.render import find_override, render_with
from modules.email_templates.schemas import (
    PreviewResponse,
    TemplateDetail,
    TemplateSummary,
    TemplateVariablePublic,
)
from packages.email.markup import variables_in
from packages.email.registry import TEMPLATES, TemplateDef, get_def, sample_values
from packages.email.service import email_service

logger = get_logger(__name__)

# A test email goes to any address the admin types, so there is a cap per person.
TEST_SENDS_PER_HOUR = 20
_recent_tests: dict[uuid.UUID, deque[float]] = defaultdict(deque)


def problems(definition: TemplateDef, subject: str, body: str) -> list[str]:
    """Why this wording can't be used (placeholders that don't exist, or a required link taken out)."""
    allowed = {v.name for v in definition.variables}
    used = variables_in(subject, body)
    found: list[str] = []
    unknown = sorted(used - allowed)
    if unknown:
        names = ", ".join("{{" + n + "}}" for n in unknown)
        available = ", ".join("{{" + n + "}}" for n in sorted(allowed))
        found.append(f"Unknown placeholder{'s' if len(unknown) > 1 else ''}: {names}. You can use: {available}.")
    for name in definition.required:
        if name not in variables_in(body):
            found.append("The message must keep {{" + name + "}}, otherwise the person has nothing to click.")
    if not subject.strip():
        found.append("The subject can't be empty.")
    if not body.strip():
        found.append("The message can't be empty.")
    return found


class EmailTemplateService:
    def __init__(self, db: AsyncSession, organization_id: uuid.UUID, hackathon_id: uuid.UUID | None = None):
        self.db = db
        self.organization_id = organization_id
        self.hackathon_id = hackathon_id

    def _definition(self, key: str) -> TemplateDef:
        definition = get_def(key)
        if definition is None or (self.hackathon_id is not None and not definition.event_scoped):
            raise NotFoundError("Email template", key)
        return definition

    async def _own_row(self, key: str) -> EmailTemplate | None:
        """The edit that belongs to this scope (the organisation's, or this hackathon's)."""
        return (
            await self.db.execute(
                select(EmailTemplate).where(
                    EmailTemplate.organization_id == self.organization_id,
                    EmailTemplate.key == key,
                    EmailTemplate.hackathon_id == self.hackathon_id
                    if self.hackathon_id is not None
                    else EmailTemplate.hackathon_id.is_(None),
                )
            )
        ).scalar_one_or_none()

    async def _names(self, rows: list[EmailTemplate]) -> dict[uuid.UUID, str]:
        ids = {r.updated_by_user_id for r in rows if r.updated_by_user_id}
        if not ids:
            return {}
        return dict((await self.db.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all())

    def _summary(self, d: TemplateDef, own: EmailTemplate | None, org_row: EmailTemplate | None, names: dict) -> dict:
        effective = own or (org_row if self.hackathon_id is not None else None)
        return dict(
            key=d.key,
            name=d.name,
            category=d.category,
            description=d.description,
            when_sent=d.when_sent,
            has_attachment=d.has_attachment,
            event_scoped=d.event_scoped,
            customised=own is not None,
            inherited=self.hackathon_id is not None and own is None,
            updated_at=effective.updated_at if effective else None,
            updated_by_name=names.get(effective.updated_by_user_id) if effective and effective.updated_by_user_id else None,
        )

    async def list_all(self) -> list[TemplateSummary]:
        scope = [d for d in TEMPLATES if self.hackathon_id is None or d.event_scoped]
        rows = (
            await self.db.execute(
                select(EmailTemplate).where(
                    EmailTemplate.organization_id == self.organization_id,
                    (EmailTemplate.hackathon_id == self.hackathon_id) | EmailTemplate.hackathon_id.is_(None),
                )
            )
        ).scalars().all()
        names = await self._names(list(rows))
        own = {r.key: r for r in rows if r.hackathon_id == self.hackathon_id}
        org = {r.key: r for r in rows if r.hackathon_id is None}
        return [TemplateSummary(**self._summary(d, own.get(d.key), org.get(d.key), names)) for d in scope]

    async def detail(self, key: str) -> TemplateDetail:
        d = self._definition(key)
        own = await self._own_row(key)
        org_row = await find_override(self.db, self.organization_id, key) if self.hackathon_id is not None else None
        effective = own or org_row
        names = await self._names([r for r in (own, org_row) if r])
        return TemplateDetail(
            **self._summary(d, own, org_row, names),
            subject=effective.subject if effective else d.subject,
            body=effective.body if effective else d.body,
            default_subject=d.subject,
            default_body=d.body,
            variables=[TemplateVariablePublic(name=v.name, description=v.description, sample=v.sample) for v in d.variables],
            required=list(d.required),
        )

    async def save(self, key: str, subject: str, body: str, user_id: uuid.UUID) -> TemplateDetail:
        d = self._definition(key)
        subject, body = subject.strip(), body.strip()
        found = problems(d, subject, body)
        if found:
            raise ValidationError(" ".join(found))
        row = await self._own_row(key)
        if row is None:
            row = EmailTemplate(
                organization_id=self.organization_id, hackathon_id=self.hackathon_id, key=key, subject=subject, body=body
            )
            self.db.add(row)
        else:
            row.subject, row.body = subject, body
        row.updated_by_user_id = user_id
        await self.db.flush()
        logger.info("email_template_saved", key=key, hackathon_id=str(self.hackathon_id) if self.hackathon_id else None)
        return await self.detail(key)

    async def reset(self, key: str) -> TemplateDetail:
        """Drop this scope's edit: back to the organisation's wording (for an event) or the built-in default."""
        self._definition(key)
        await self.db.execute(
            delete(EmailTemplate).where(
                EmailTemplate.organization_id == self.organization_id,
                EmailTemplate.key == key,
                EmailTemplate.hackathon_id == self.hackathon_id
                if self.hackathon_id is not None
                else EmailTemplate.hackathon_id.is_(None),
            )
        )
        await self.db.flush()
        return await self.detail(key)

    def preview(self, key: str, subject: str, body: str) -> PreviewResponse:
        d = self._definition(key)
        subject_out, text, html = render_with(d, subject, body, sample_values(d))
        return PreviewResponse(subject=subject_out, html=html, text=text, errors=problems(d, subject, body))

    async def send_test(
        self, key: str, to_email: str, user_id: uuid.UUID, subject: str | None, body: str | None
    ) -> tuple[bool, str]:
        """Send the (draft or saved) wording with sample values to one address, and say honestly whether the
        mail server accepted it."""
        d = self._definition(key)
        if subject is None or body is None:
            saved = await self.detail(key)
            subject, body = saved.subject, saved.body
        found = problems(d, subject, body)
        if found:
            raise ValidationError(" ".join(found))

        now = time.monotonic()
        recent = _recent_tests[user_id]
        while recent and now - recent[0] > 3600:
            recent.popleft()
        if len(recent) >= TEST_SENDS_PER_HOUR:
            raise RateLimitError(f"You can send {TEST_SENDS_PER_HOUR} test emails an hour. Try again later.")
        recent.append(now)

        subject_out, text, html = render_with(d, subject, body, sample_values(d))
        note = "This is a test email: the details above are sample values, and no one else received it."
        sent = await email_service.send(
            to_email,
            f"[TEST] {subject_out}",
            f"{text}\n\n--\n{note}",
            html.replace("</div>", f'<p style="color:#9ca3af;font-size:12px">{note}</p></div>', 1)
            if html.endswith("</div>")
            else html,
        )
        if sent:
            return True, f"Sent to {to_email}. Check that inbox (and the spam folder)."
        return False, (
            "The mail server did not accept the message, so nothing was sent. "
            "Check the SMTP settings (host, port, user, password and from-address) on the server."
        )
