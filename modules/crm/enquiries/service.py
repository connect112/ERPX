import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.crm.enquiries.models import Enquiry
from modules.crm.enquiries.repository import EnquiryRepository
from modules.crm.leads.repository import LeadRepository

logger = get_logger(__name__)


class EnquiryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EnquiryRepository(db)
        self.lead_repo = LeadRepository(db)

    async def _get_owned_lead(self, lead_id: uuid.UUID, organization_id: uuid.UUID):
        lead = await self.lead_repo.get_by_id(lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", lead_id)
        return lead

    async def create_enquiry(
        self, lead_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Enquiry:
        await self._get_owned_lead(lead_id, organization_id)
        enquiry = await self.repo.create(lead_id=lead_id, **fields)
        logger.info("enquiry_created", enquiry_id=str(enquiry.id), lead_id=str(lead_id))
        return enquiry

    async def list_enquiries(self, lead_id: uuid.UUID, organization_id: uuid.UUID) -> list[Enquiry]:
        await self._get_owned_lead(lead_id, organization_id)
        return await self.repo.list_for_lead(lead_id)

    async def get_enquiry(
        self, enquiry_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Enquiry:
        await self._get_owned_lead(lead_id, organization_id)
        enquiry = await self.repo.get_by_id(enquiry_id)
        if not enquiry or enquiry.lead_id != lead_id:
            raise NotFoundError("Enquiry", enquiry_id)
        return enquiry

    async def update_enquiry(
        self, enquiry_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Enquiry:
        enquiry = await self.get_enquiry(enquiry_id, lead_id, organization_id)
        updated = await self.repo.update(enquiry, **fields)
        logger.info("enquiry_updated", enquiry_id=str(enquiry_id))
        return updated

    async def delete_enquiry(
        self, enquiry_id: uuid.UUID, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        enquiry = await self.get_enquiry(enquiry_id, lead_id, organization_id)
        await self.repo.delete(enquiry)
        logger.info("enquiry_deleted", enquiry_id=str(enquiry_id))
