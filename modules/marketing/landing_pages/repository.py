import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.marketing.landing_pages.models import LandingPage, LandingPageStatus, LandingPageView


class LandingPageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> LandingPage:
        page = LandingPage(**fields)
        self.db.add(page)
        await self.db.flush()
        await self.db.refresh(page)
        return page

    async def get_by_id(self, page_id: uuid.UUID, organization_id: uuid.UUID) -> LandingPage | None:
        result = await self.db.execute(
            select(LandingPage).where(LandingPage.id == page_id, LandingPage.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, organization_id: uuid.UUID, slug: str) -> LandingPage | None:
        result = await self.db.execute(
            select(LandingPage).where(LandingPage.organization_id == organization_id, LandingPage.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id_public(self, page_id: uuid.UUID) -> LandingPage | None:
        """Organization-unscoped lookup by primary key, for the anonymous view-tracking beacon only."""
        result = await self.db.execute(select(LandingPage).where(LandingPage.id == page_id))
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID | None = None,
        status: LandingPageStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[LandingPage], int]:
        conditions = [LandingPage.organization_id == organization_id]
        if campaign_id is not None:
            conditions.append(LandingPage.campaign_id == campaign_id)
        if status is not None:
            conditions.append(LandingPage.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(LandingPage).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(LandingPage).where(*conditions).order_by(LandingPage.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, page: LandingPage, **fields) -> LandingPage:
        for key, value in fields.items():
            if value is not None:
                setattr(page, key, value)
        await self.db.flush()
        await self.db.refresh(page)
        return page


class LandingPageViewRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> LandingPageView:
        view = LandingPageView(**fields)
        self.db.add(view)
        await self.db.flush()
        await self.db.refresh(view)
        return view

    async def count_for_page(self, landing_page_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(LandingPageView).where(LandingPageView.landing_page_id == landing_page_id)
        )
        return result.scalar_one()

    async def count_for_pages(self, landing_page_ids: list[uuid.UUID]) -> int:
        """Total views across many pages in one query.

        The sum of per-page ``count_for_page`` values equals ``COUNT(*)`` over
        all those pages' view rows — replacing an N+1 (one count per page) with
        a single scan. An empty id list short-circuits to 0 without a query.
        """
        if not landing_page_ids:
            return 0
        result = await self.db.execute(
            select(func.count())
            .select_from(LandingPageView)
            .where(LandingPageView.landing_page_id.in_(landing_page_ids))
        )
        return result.scalar_one()

    async def count_conversions_for_page(self, landing_page_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(LandingPageView)
            .where(
                LandingPageView.landing_page_id == landing_page_id,
                LandingPageView.converted_to_lead_id.is_not(None),
            )
        )
        return result.scalar_one()

    async def list_for_page(self, landing_page_id: uuid.UUID, skip: int = 0, limit: int = 50) -> tuple[list[LandingPageView], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(LandingPageView).where(LandingPageView.landing_page_id == landing_page_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(LandingPageView)
            .where(LandingPageView.landing_page_id == landing_page_id)
            .order_by(LandingPageView.viewed_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total
