import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.crm.leads.models import Lead, LeadStatus
from modules.crm.leads.repository import LeadRepository

logger = get_logger(__name__)

# Valid forward transitions. Leads can always move to LOST from any
# non-terminal state, and CONVERTED is terminal (reached via Admissions).
_ALLOWED_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {LeadStatus.CONTACTED, LeadStatus.LOST},
    LeadStatus.CONTACTED: {LeadStatus.QUALIFIED, LeadStatus.LOST},
    LeadStatus.QUALIFIED: {LeadStatus.CONVERTED, LeadStatus.LOST},
    LeadStatus.CONVERTED: set(),
    LeadStatus.LOST: {LeadStatus.NEW},  # allow re-opening a lost lead
}


class LeadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LeadRepository(db)

    async def create_lead(self, organization_id: uuid.UUID, **fields) -> Lead:
        lead = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("lead_created", lead_id=str(lead.id), org_id=str(organization_id))
        return lead

    async def get_lead(self, lead_id: uuid.UUID, organization_id: uuid.UUID) -> Lead:
        lead = await self.repo.get_by_id(lead_id, organization_id)
        if not lead:
            raise NotFoundError("Lead", lead_id)
        return lead

    async def list_leads(self, organization_id: uuid.UUID, **filters) -> tuple[list[Lead], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_lead(self, lead_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Lead:
        lead = await self.get_lead(lead_id, organization_id)
        updated = await self.repo.update(lead, **fields)
        logger.info("lead_updated", lead_id=str(lead_id))
        return updated

    async def change_status(
        self,
        lead_id: uuid.UUID,
        organization_id: uuid.UUID,
        new_status: LeadStatus,
        lost_reason: str | None,
    ) -> Lead:
        lead = await self.get_lead(lead_id, organization_id)

        if new_status != lead.status:
            allowed = _ALLOWED_TRANSITIONS.get(lead.status, set())
            if new_status not in allowed:
                raise ValidationError(
                    f"Cannot move a lead from '{lead.status.value}' to '{new_status.value}'."
                )
        if new_status == LeadStatus.LOST and not lost_reason:
            raise ValidationError("A reason is required when marking a lead as lost.")

        updated = await self.repo.set_status(lead, new_status, lost_reason)
        logger.info("lead_status_changed", lead_id=str(lead_id), status=new_status.value)
        return updated

    async def delete_lead(self, lead_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        lead = await self.get_lead(lead_id, organization_id)
        await self.repo.soft_delete(lead)
        logger.info("lead_deleted", lead_id=str(lead_id))
