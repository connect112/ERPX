"""
Shared email package.

Every module that needs to send email (Authentication for verification/
password reset, Notifications for digests, Accounting for invoice
delivery, HR for payslips, Reports for scheduled exports, ...) imports
`EmailService` from here instead of talking to SMTP directly. Templates
are plain-text + HTML pairs kept in `templates.py` so copy changes never
touch sending logic.
"""

import ssl
from dataclasses import dataclass

import aiosmtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging_config import get_logger
from packages.email.history import record_send, take_send_meta

logger = get_logger(__name__)


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    mime_type: str = "application/octet-stream"


class EmailService:
    def __init__(self) -> None:
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME

    async def send(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> bool:
        meta = take_send_meta()  # which template made this email (left by the renderer), for the send history
        sender_name = " ".join((meta.from_name if meta else "").split()) or self.from_name
        message = EmailMessage()
        message["From"] = f"{sender_name.replace(chr(34), '')} <{self.from_email}>"
        message["To"] = to_email
        message["Subject"] = " ".join(str(subject).split())  # one line: a subject can never add a header
        if meta and meta.reply_to and "@" in meta.reply_to and not any(c in meta.reply_to for c in ("\r", "\n", "<", ">", ",", ";")):
            message["Reply-To"] = meta.reply_to
        for name, value in (meta.headers if meta else {}).items():
            if name.replace('-', '').isalnum() and not any(c in str(value) for c in ('\r', '\n')):
                message[name] = str(value)
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        if meta and meta.requires and not attachments:
            missing = ", ".join(meta.requires)
            logger.warning("email_required_attachment_missing", to=to_email, subject=subject, missing=missing)
            await record_send(meta, to_email, subject, False, f"Not sent: the required attachment is missing ({missing}).", 0)
            return False
        all_attachments = list(attachments or []) + list(meta.extra_attachments if meta else [])
        for attachment in all_attachments:
            maintype, _, subtype = attachment.mime_type.partition("/")
            message.add_attachment(
                attachment.content,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )

        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username or None,
                password=self.password or None,
                start_tls=self.port == 587,
                tls_context=ssl.create_default_context(),
            )
            logger.info("email_sent", to=to_email, subject=subject)
            await record_send(meta, to_email, subject, True, None, len(all_attachments))
            return True
        except Exception as exc:
            logger.exception("email_send_failed", to=to_email, subject=subject)
            await record_send(meta, to_email, subject, False, f"{type(exc).__name__}: {exc}"[:400], len(all_attachments))
            return False


email_service = EmailService()
