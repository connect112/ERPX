import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.crm.leads.models import Lead, LeadStatus


class LeadRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Lead:
        lead = Lead(**fields)
        self.db.add(lead)
        await self.db.flush()
        await self.db.refresh(lead)
        return lead

    async def get_by_id(self, lead_id: uuid.UUID, organization_id: uuid.UUID) -> Lead | None:
        result = await self.db.execute(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == organization_id,
                Lead.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: LeadStatus | None = None,
        assigned_to_user_id: uuid.UUID | None = None,
        campaign_id: uuid.UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Lead], int]:
        conditions = [Lead.organization_id == organization_id, Lead.deleted_at.is_(None)]
        if status is not None:
            conditions.append(Lead.status == status)
        if assigned_to_user_id is not None:
            conditions.append(Lead.assigned_to_user_id == assigned_to_user_id)
        if campaign_id is not None:
            conditions.append(Lead.campaign_id == campaign_id)
        if search:
            like_pattern = f"%{search}%"
            conditions.append(
                (Lead.full_name.ilike(like_pattern))
                | (Lead.email.ilike(like_pattern))
                | (Lead.phone.ilike(like_pattern))
            )

        count_result = await self.db.execute(
            select(func.count()).select_from(Lead).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Lead)
            .where(*conditions)
            .order_by(Lead.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def count_for_campaigns(
        self, organization_id: uuid.UUID, campaign_ids: list[uuid.UUID]
    ) -> int:
        """Total non-deleted leads attributed to any of the given campaigns, in
        one query. A lead carries a single ``campaign_id``, so a ``campaign_id IN
        (...)`` count equals the sum of the per-campaign counts
        ``list_for_organization(campaign_id=...)`` returns — same
        organization + ``deleted_at IS NULL`` filter — replacing that N+1."""
        if not campaign_ids:
            return 0
        result = await self.db.execute(
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.deleted_at.is_(None),
                Lead.campaign_id.in_(campaign_ids),
            )
        )
        return result.scalar_one()

    async def update(self, lead: Lead, **fields) -> Lead:
        for key, value in fields.items():
            if value is not None:
                setattr(lead, key, value)
        await self.db.flush()
        await self.db.refresh(lead)
        return lead

    async def set_status(
        self, lead: Lead, status: LeadStatus, lost_reason: str | None = None
    ) -> Lead:
        lead.status = status
        if status == LeadStatus.LOST:
            lead.lost_reason = lost_reason
        await self.db.flush()
        await self.db.refresh(lead)
        return lead

    async def soft_delete(self, lead: Lead) -> None:
        from datetime import datetime, timezone

        lead.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
