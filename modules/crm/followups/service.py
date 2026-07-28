import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.crm.followups.models import FollowUp, FollowUpType
from modules.crm.followups.repository import FollowUpRepository
from modules.crm.followups.tasks import send_followup_sms_task, send_followup_whatsapp_task
from modules.crm.leads.repository import LeadRepository

logger = get_logger(__name__)

_NOTIFY_TASKS = {
    FollowUpType.WHATSAPP: send_followup_whatsapp_task,
    FollowUpType.SMS: send_followup_sms_task,
}


class FollowUpService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FollowUpRepository(db)
        self.lead_repo = LeadRepository(db)

    async def _get_owned_lead(self, lead_id: uuid.UUID, organization_id: uuid.UUID):
        lead = await self.lead_repo.get_by_id(lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", lead_id)
        return lead

    async def create_followup(
        self, lead_id: uuid.UUID, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, **fields
    ) -> FollowUp:
        lead = await self._get_owned_lead(lead_id, organization_id)
        followup = await self.repo.create(
            lead_id=lead_id, created_by_user_id=created_by_user_id, **fields
        )
        logger.info("followup_created", followup_id=str(followup.id), lead_id=str(lead_id))

        notify_task = _NOTIFY_TASKS.get(followup.follow_up_type)
        if notify_task and lead.phone:
            notify_task.delay(lead.phone, lead.full_name, followup.scheduled_at.isoformat())
            logger.info(
                "followup_reminder_dispatched",
                followup_id=str(followup.id),
                channel=followup.follow_up_type.value,
            )

        return followup

    async def list_followups(self, lead_id: uuid.UUID, organization_id: uuid.UUID) -> list[FollowUp]:
        await self._get_owned_lead(lead_id, organization_id)
        return await self.repo.list_for_lead(lead_id)

    async def get_followup(
        self, followup_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> FollowUp:
        await self._get_owned_lead(lead_id, organization_id)
        followup = await self.repo.get_by_id(followup_id)
        if not followup or followup.lead_id != lead_id:
            raise NotFoundError("Follow-up", followup_id)
        return followup

    async def update_followup(
        self, followup_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> FollowUp:
        followup = await self.get_followup(followup_id, lead_id, organization_id)
        updated = await self.repo.update(followup, **fields)
        logger.info("followup_updated", followup_id=str(followup_id))
        return updated

    async def complete_followup(
        self,
        followup_id: uuid.UUID,
        lead_id: uuid.UUID,
        organization_id: uuid.UUID,
        outcome: str,
        notes: str | None,
    ) -> FollowUp:
        followup = await self.get_followup(followup_id, lead_id, organization_id)
        completed = await self.repo.mark_completed(followup, outcome, notes)
        logger.info("followup_completed", followup_id=str(followup_id))
        return completed

    async def delete_followup(
        self, followup_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        followup = await self.get_followup(followup_id, lead_id, organization_id)
        await self.repo.delete(followup)
        logger.info("followup_deleted", followup_id=str(followup_id))
