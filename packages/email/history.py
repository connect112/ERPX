"""
Remembering which template made an email, and recording how its sending ended.

Rendering an email (`modules.email_templates.render`) leaves a small note about it here; `EmailService.send` picks the note up,
sends, and writes one row to the send history. Doing it at this one place means every sender (account emails, certificates, payroll,
announcements, offer letters...) is covered without each of them being changed.

Recording is best effort: a problem with the history never stops, delays or fails an email. Message bodies and links are not
recorded, so reset and verification tokens never reach the history.
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from app.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SendMeta:
    organization_id: uuid.UUID | None = None
    key: str | None = None
    module: str | None = None
    template_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    source: str | None = None
    is_test: bool = False
    idempotency_key: str | None = None
    sent_by_user_id: uuid.UUID | None = None
    reply_to: str = ""
    from_name: str = ""
    extra_attachments: list[Any] = field(default_factory=list)
    # Extra message headers, e.g. List-Unsubscribe. Values with a line break are dropped.
    headers: dict[str, str] = field(default_factory=dict)
    # names of recipient-specific documents the template needs (an offer letter, a certificate); sending refuses to go without one
    requires: list[str] = field(default_factory=list)


_current: ContextVar[SendMeta | None] = ContextVar("email_send_meta", default=None)


def set_send_meta(meta: SendMeta) -> None:
    _current.set(meta)


def take_send_meta() -> SendMeta | None:
    """The note left by the last render in this task (and forget it, so it can never apply to another email)."""
    meta = _current.get()
    _current.set(None)
    return meta


async def record_send(meta: SendMeta | None, to_email: str, subject: str, ok: bool, error: str | None, attachments: int) -> None:
    from app.db.session import get_db_context
    from modules.email_studio.models import EmailSendRecord, SendStatus

    meta = meta or SendMeta()
    try:
        async with get_db_context() as db:
            db.add(
                EmailSendRecord(
                    organization_id=meta.organization_id,
                    key=meta.key,
                    module=meta.module,
                    template_id=meta.template_id,
                    version_id=meta.version_id,
                    source=meta.source,
                    recipient=to_email.strip().lower()[:255],
                    subject=(subject or "")[:300],
                    status=(SendStatus.SENT if ok else SendStatus.FAILED).value,
                    error=None if ok else (error or "The mail server did not accept the message.")[:500],
                    attachments=attachments,
                    is_test=meta.is_test,
                    idempotency_key=meta.idempotency_key,
                    sent_by_user_id=meta.sent_by_user_id,
                )
            )
            await db.flush()
    except Exception:  # noqa: BLE001 - the history must never get in the way of an email
        logger.warning("email_history_record_failed", exc_info=True)
