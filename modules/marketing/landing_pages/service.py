import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.marketing.campaigns.repository import CampaignRepository
from modules.marketing.landing_pages.models import LandingPage, LandingPageStatus, LandingPageView
from modules.marketing.landing_pages.repository import LandingPageRepository, LandingPageViewRepository

logger = get_logger(__name__)


class LandingPageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LandingPageRepository(db)
        self.campaign_repo = CampaignRepository(db)
        self.view_repo = LandingPageViewRepository(db)

    async def create_page(
        self, organization_id: uuid.UUID, slug: str, campaign_id: uuid.UUID | None = None, **fields
    ) -> LandingPage:
        existing = await self.repo.get_by_slug(organization_id, slug)
        if existing:
            raise ConflictError(f"A landing page with slug '{slug}' already exists.")
        if campaign_id is not None:
            campaign = await self.campaign_repo.get_by_id(campaign_id, organization_id)
            if not campaign:
                raise NotFoundError("Campaign", campaign_id)

        page = await self.repo.create(organization_id=organization_id, slug=slug, campaign_id=campaign_id, **fields)
        logger.info("landing_page_created", page_id=str(page.id), slug=slug)
        return page

    async def get_page(self, page_id: uuid.UUID, organization_id: uuid.UUID) -> LandingPage:
        page = await self.repo.get_by_id(page_id, organization_id)
        if not page:
            raise NotFoundError("Landing page", page_id)
        return page

    async def list_pages(self, organization_id: uuid.UUID, **filters) -> tuple[list[LandingPage], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_page(self, page_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> LandingPage:
        page = await self.get_page(page_id, organization_id)
        if page.status == LandingPageStatus.ARCHIVED:
            raise ValidationError("An archived landing page cannot be edited.")
        updated = await self.repo.update(page, **fields)
        logger.info("landing_page_updated", page_id=str(page_id))
        return updated

    async def publish_page(self, page_id: uuid.UUID, organization_id: uuid.UUID) -> LandingPage:
        page = await self.get_page(page_id, organization_id)
        if page.status != LandingPageStatus.DRAFT:
            raise ValidationError(f"Only draft pages can be published (this one is '{page.status.value}').")
        updated = await self.repo.update(
            page, status=LandingPageStatus.PUBLISHED, published_at=datetime.now(timezone.utc)
        )
        logger.info("landing_page_published", page_id=str(page_id))
        return updated

    async def archive_page(self, page_id: uuid.UUID, organization_id: uuid.UUID) -> LandingPage:
        page = await self.get_page(page_id, organization_id)
        if page.status != LandingPageStatus.PUBLISHED:
            raise ValidationError("Only published pages can be archived.")
        updated = await self.repo.update(page, status=LandingPageStatus.ARCHIVED)
        logger.info("landing_page_archived", page_id=str(page_id))
        return updated

    async def record_public_view(self, page_id: uuid.UUID, **fields) -> LandingPageView:
        """
        Called from the anonymous tracking beacon on a published page —
        deliberately organization-unscoped (an anonymous visitor has no
        authenticated organization context); the page is looked up by
        primary key alone, and only PUBLISHED pages accept views.
        """
        page = await self.repo.get_by_id_public(page_id)
        if not page:
            raise NotFoundError("Landing page", page_id)
        if page.status != LandingPageStatus.PUBLISHED:
            raise ValidationError("Only published pages can record views.")
        view = await self.view_repo.create(
            landing_page_id=page_id, viewed_at=datetime.now(timezone.utc), **fields
        )
        return view

    async def mark_conversion(self, view_id: uuid.UUID, lead_id: uuid.UUID) -> None:
        """Not exposed as its own route — called by CRM's lead-creation flow when a lead came from a tracked view."""
        from sqlalchemy import select

        result = await self.db.execute(select(LandingPageView).where(LandingPageView.id == view_id))
        view = result.scalar_one_or_none()
        if not view:
            raise NotFoundError("Landing page view", view_id)
        view.converted_to_lead_id = lead_id
        await self.db.flush()

    async def get_stats(self, page_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
        await self.get_page(page_id, organization_id)
        total_views = await self.view_repo.count_for_page(page_id)
        total_conversions = await self.view_repo.count_conversions_for_page(page_id)
        conversion_rate = round((total_conversions / total_views) * 100, 2) if total_views > 0 else 0.0
        return {
            "landing_page_id": page_id,
            "total_views": total_views,
            "total_conversions": total_conversions,
            "conversion_rate_percent": conversion_rate,
        }

    async def list_views(self, page_id: uuid.UUID, organization_id: uuid.UUID, **filters):
        await self.get_page(page_id, organization_id)
        return await self.view_repo.list_for_page(page_id, **filters)
