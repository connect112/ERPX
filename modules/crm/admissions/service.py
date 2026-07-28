import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.crm.admissions.models import Admission, AdmissionStatus
from modules.crm.admissions.repository import AdmissionRepository
from modules.crm.leads.models import LeadStatus
from modules.crm.leads.repository import LeadRepository

logger = get_logger(__name__)


class AdmissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdmissionRepository(db)
        self.lead_repo = LeadRepository(db)

    async def create_admission(
        self, lead_id: uuid.UUID, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, **fields
    ) -> Admission:
        lead = await self.lead_repo.get_by_id(lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", lead_id)

        if lead.status == LeadStatus.CONVERTED:
            existing = await self.repo.get_by_lead_id(lead_id)
            if existing:
                raise ConflictError("This lead already has an admission record.")

        if lead.status == LeadStatus.LOST:
            raise ValidationError("Cannot admit a lead that has been marked as lost.")

        admission = await self.repo.create(
            lead_id=lead_id,
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            **fields,
        )

        if lead.status != LeadStatus.CONVERTED:
            await self.lead_repo.set_status(lead, LeadStatus.CONVERTED)

        logger.info("admission_created", admission_id=str(admission.id), lead_id=str(lead_id))
        return admission

    async def get_admission(self, admission_id: uuid.UUID, organization_id: uuid.UUID) -> Admission:
        admission = await self.repo.get_by_id(admission_id, organization_id)
        if not admission:
            raise NotFoundError("Admission", admission_id)
        return admission

    async def get_admission_for_lead(
        self, lead_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Admission:
        lead = await self.lead_repo.get_by_id(lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", lead_id)
        admission = await self.repo.get_by_lead_id(lead_id)
        if not admission:
            raise NotFoundError("Admission for this lead", lead_id)
        return admission

    async def list_admissions(self, organization_id: uuid.UUID) -> list[Admission]:
        return await self.repo.list_for_organization(organization_id)

    async def update_admission(
        self, admission_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Admission:
        admission = await self.get_admission(admission_id, organization_id)
        updated = await self.repo.update(admission, **fields)
        logger.info("admission_updated", admission_id=str(admission_id))
        return updated

    async def cancel_admission(self, admission_id: uuid.UUID, organization_id: uuid.UUID) -> Admission:
        admission = await self.get_admission(admission_id, organization_id)
        cancelled = await self.repo.update(admission, status=AdmissionStatus.CANCELLED)
        logger.info("admission_cancelled", admission_id=str(admission_id))
        return cancelled
