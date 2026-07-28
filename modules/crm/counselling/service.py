import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.crm.counselling.models import CounsellingSession
from modules.crm.counselling.repository import CounsellingRepository
from modules.crm.leads.repository import LeadRepository

logger = get_logger(__name__)


class CounsellingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CounsellingRepository(db)
        self.lead_repo = LeadRepository(db)

    async def _get_owned_lead(self, lead_id: uuid.UUID, organization_id: uuid.UUID):
        lead = await self.lead_repo.get_by_id(lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", lead_id)
        return lead

    async def create_session(
        self, lead_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> CounsellingSession:
        await self._get_owned_lead(lead_id, organization_id)
        session = await self.repo.create(lead_id=lead_id, **fields)
        logger.info("counselling_session_created", session_id=str(session.id), lead_id=str(lead_id))
        return session

    async def list_sessions(
        self, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[CounsellingSession]:
        await self._get_owned_lead(lead_id, organization_id)
        return await self.repo.list_for_lead(lead_id)

    async def get_session(
        self, session_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> CounsellingSession:
        await self._get_owned_lead(lead_id, organization_id)
        session = await self.repo.get_by_id(session_id)
        if not session or session.lead_id != lead_id:
            raise NotFoundError("Counselling session", session_id)
        return session

    async def update_session(
        self, session_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> CounsellingSession:
        session = await self.get_session(session_id, lead_id, organization_id)
        updated = await self.repo.update(session, **fields)
        logger.info("counselling_session_updated", session_id=str(session_id))
        return updated

    async def complete_session(
        self,
        session_id: uuid.UUID,
        lead_id: uuid.UUID,
        organization_id: uuid.UUID,
        recommended_course: str | None,
        notes: str | None,
    ) -> CounsellingSession:
        session = await self.get_session(session_id, lead_id, organization_id)
        completed = await self.repo.mark_completed(session, recommended_course, notes)
        logger.info("counselling_session_completed", session_id=str(session_id))
        return completed

    async def delete_session(
        self, session_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        session = await self.get_session(session_id, lead_id, organization_id)
        await self.repo.delete(session)
        logger.info("counselling_session_deleted", session_id=str(session_id))
