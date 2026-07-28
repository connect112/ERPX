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
        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        for attachment in attachments or []:
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
            return True
        except Exception:
            logger.exception("email_send_failed", to=to_email, subject=subject)
            return False


email_service = EmailService()
