import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.marketing.campaigns.models import Campaign, CampaignChannel, CampaignStatus


class CampaignRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Campaign:
        campaign = Campaign(**fields)
        self.db.add(campaign)
        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign

    async def get_by_id(self, campaign_id: uuid.UUID, organization_id: uuid.UUID) -> Campaign | None:
        result = await self.db.execute(
            select(Campaign).where(Campaign.id == campaign_id, Campaign.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, campaign_code: str) -> Campaign | None:
        result = await self.db.execute(
            select(Campaign).where(
                Campaign.organization_id == organization_id, Campaign.campaign_code == campaign_code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        channel: CampaignChannel | None = None,
        status: CampaignStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Campaign], int]:
        conditions = [Campaign.organization_id == organization_id]
        if channel is not None:
            conditions.append(Campaign.channel == channel)
        if status is not None:
            conditions.append(Campaign.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(Campaign).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Campaign).where(*conditions).order_by(Campaign.start_date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, campaign: Campaign, **fields) -> Campaign:
        for key, value in fields.items():
            if value is not None:
                setattr(campaign, key, value)
        await self.db.flush()
        await self.db.refresh(campaign)
        return campaign
