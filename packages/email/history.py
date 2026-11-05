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

# How the last send in this task ended: "accepted", "refused" (the mail server or the network refused it before taking the message,
# so it was definitely not delivered) or "unknown" (the connection broke or timed out after the message may have been handed over).
# Callers that must not guess (an email carrying a personal link) read it; everything else can keep using the True/False result.
_outcome: ContextVar[str | None] = ContextVar("email_send_outcome", default=None)


def set_send_outcome(outcome: str | None) -> None:
    _outcome.set(outcome)


def take_send_outcome() -> str | None:
    outcome = _outcome.get()
    _outcome.set(None)
    return outcome


def redact(text: str | None, secrets: list[str]) -> str:
    """The text with each secret (a raw link or token) replaced, for anything that is stored or logged."""
    out = text or ""
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[removed]")
    return out


def set_send_meta(meta: SendMeta) -> None:
    _current.set(meta)


def take_send_meta() -> SendMeta | None:
    """The note left by the last render in this task (and forget it, so it can never apply to another email)."""
    meta = _current.get()
    _current.set(None)
    return meta


def record_failure(db: Any, meta: SendMeta | None, to_email: str, subject: str, error: str) -> None:
    """Add a failed row to the send history for an email that was never handed to the mail server (for example its template could not
    be rendered), in the caller's own database session, so it is written or rolled back together with the caller's other records."""
    from modules.email_studio.models import EmailSendRecord, SendStatus

    meta = meta or SendMeta()
    db.add(
        EmailSendRecord(
            organization_id=meta.organization_id, key=meta.key, module=meta.module, template_id=meta.template_id, version_id=meta.version_id,
            source=meta.source, recipient=to_email.strip().lower()[:255], subject=(subject or "")[:300], status=SendStatus.FAILED.value,
            error=(error or "The email could not be made.")[:500], attachments=0, is_test=meta.is_test, idempotency_key=meta.idempotency_key,
            sent_by_user_id=meta.sent_by_user_id,
        )
    )


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
