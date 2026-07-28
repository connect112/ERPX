import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.marketing.campaigns.models import Campaign
from modules.marketing.campaigns.repository import CampaignRepository

logger = get_logger(__name__)


class CampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CampaignRepository(db)

    async def create_campaign(
        self, organization_id: uuid.UUID, campaign_code: str, created_by_user_id: uuid.UUID | None = None, **fields
    ) -> Campaign:
        existing = await self.repo.get_by_code(organization_id, campaign_code)
        if existing:
            raise ConflictError(f"A campaign with code '{campaign_code}' already exists.")
        campaign = await self.repo.create(
            organization_id=organization_id,
            campaign_code=campaign_code,
            created_by_user_id=created_by_user_id,
            **fields,
        )
        logger.info("campaign_created", campaign_id=str(campaign.id), campaign_code=campaign_code)
        return campaign

    async def get_campaign(self, campaign_id: uuid.UUID, organization_id: uuid.UUID) -> Campaign:
        campaign = await self.repo.get_by_id(campaign_id, organization_id)
        if not campaign:
            raise NotFoundError("Campaign", campaign_id)
        return campaign

    async def list_campaigns(self, organization_id: uuid.UUID, **filters) -> tuple[list[Campaign], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_campaign(self, campaign_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Campaign:
        campaign = await self.get_campaign(campaign_id, organization_id)
        updated = await self.repo.update(campaign, **fields)
        logger.info("campaign_updated", campaign_id=str(campaign_id))
        return updated

    async def change_status(self, campaign_id: uuid.UUID, organization_id: uuid.UUID, status) -> Campaign:
        campaign = await self.get_campaign(campaign_id, organization_id)
        updated = await self.repo.update(campaign, status=status)
        logger.info("campaign_status_changed", campaign_id=str(campaign_id), status=status.value)
        return updated
