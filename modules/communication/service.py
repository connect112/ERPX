import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.communication.models import CommunicationChannel, CommunicationLog, CommunicationStatus
from modules.communication.repository import CommunicationLogRepository
from packages.email.service import email_service
from packages.sms.client import sms_service
from packages.whatsapp.client import whatsapp_service

logger = get_logger(__name__)


class CommunicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CommunicationLogRepository(db)

    async def record(
        self,
        organization_id: uuid.UUID,
        channel: CommunicationChannel,
        recipient: str,
        body: str,
        status: CommunicationStatus,
        subject: str | None = None,
        error_message: str | None = None,
        related_entity_type: str | None = None,
        related_entity_id: uuid.UUID | None = None,
        sent_by_user_id: uuid.UUID | None = None,
    ) -> CommunicationLog:
        """Generic write path — other modules that already send via
        packages.email/sms/whatsapp themselves can log here directly."""
        log = await self.repo.create(
            organization_id=organization_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            status=status,
            error_message=error_message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            sent_by_user_id=sent_by_user_id,
            sent_at=datetime.now(timezone.utc),
        )
        return log

    async def send_and_log(
        self,
        organization_id: uuid.UUID,
        channel: CommunicationChannel,
        recipient: str,
        body: str,
        subject: str | None = None,
        sent_by_user_id: uuid.UUID | None = None,
    ) -> CommunicationLog:
        if channel == CommunicationChannel.EMAIL:
            if not subject:
                raise ValidationError("Email communications require a subject.")
            success = await email_service.send(recipient, subject, body)
        elif channel == CommunicationChannel.SMS:
            success = await sms_service.send(recipient, body)
        elif channel == CommunicationChannel.WHATSAPP:
            success = await whatsapp_service.send_text(recipient, body)
        else:
            raise ValidationError(f"Unsupported channel: {channel}")

        status = CommunicationStatus.SENT if success else CommunicationStatus.FAILED
        error_message = None if success else "The delivery provider reported a send failure."

        log = await self.record(
            organization_id,
            channel,
            recipient,
            body,
            status,
            subject=subject,
            error_message=error_message,
            sent_by_user_id=sent_by_user_id,
        )
        logger.info(
            "communication_sent", log_id=str(log.id), channel=channel.value, status=status.value
        )
        return log

    async def get_log(self, log_id: uuid.UUID, organization_id: uuid.UUID) -> CommunicationLog:
        log = await self.repo.get_by_id(log_id, organization_id)
        if not log:
            raise NotFoundError("Communication log", log_id)
        return log

    async def list_logs(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)
