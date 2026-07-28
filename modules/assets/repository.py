import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assets.models import Asset, AssetCategory, AssetStatus, DepreciationEntry, DepreciationRun, DepreciationRunStatus


class AssetCategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AssetCategory:
        category = AssetCategory(**fields)
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def get_by_id(self, category_id: uuid.UUID, organization_id: uuid.UUID) -> AssetCategory | None:
        result = await self.db.execute(
            select(AssetCategory).where(
                AssetCategory.id == category_id, AssetCategory.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> AssetCategory | None:
        result = await self.db.execute(
            select(AssetCategory).where(
                AssetCategory.organization_id == organization_id, AssetCategory.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[AssetCategory]:
        conditions = [AssetCategory.organization_id == organization_id]
        if is_active is not None:
            conditions.append(AssetCategory.is_active == is_active)
        result = await self.db.execute(select(AssetCategory).where(*conditions).order_by(AssetCategory.name.asc()))
        return list(result.scalars().all())

    async def update(self, category: AssetCategory, **fields) -> AssetCategory:
        for key, value in fields.items():
            if value is not None:
                setattr(category, key, value)
        await self.db.flush()
        await self.db.refresh(category)
        return category


class AssetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Asset:
        asset = Asset(**fields)
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset

    async def get_by_id(self, asset_id: uuid.UUID, organization_id: uuid.UUID) -> Asset | None:
        result = await self.db.execute(
            select(Asset).where(Asset.id == asset_id, Asset.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, asset_code: str) -> Asset | None:
        result = await self.db.execute(
            select(Asset).where(Asset.organization_id == organization_id, Asset.asset_code == asset_code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        category_id: uuid.UUID | None = None,
        status: AssetStatus | None = None,
        assigned_to_employee_id: uuid.UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Asset], int]:
        conditions = [Asset.organization_id == organization_id]
        if category_id is not None:
            conditions.append(Asset.category_id == category_id)
        if status is not None:
            conditions.append(Asset.status == status)
        if assigned_to_employee_id is not None:
            conditions.append(Asset.assigned_to_employee_id == assigned_to_employee_id)
        if search:
            like_pattern = f"%{search}%"
            conditions.append((Asset.name.ilike(like_pattern)) | (Asset.asset_code.ilike(like_pattern)))

        count_result = await self.db.execute(select(func.count()).select_from(Asset).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Asset).where(*conditions).order_by(Asset.asset_code.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_depreciable(self, organization_id: uuid.UUID) -> list[Asset]:
        result = await self.db.execute(
            select(Asset).where(
                Asset.organization_id == organization_id, Asset.status != AssetStatus.DISPOSED
            )
        )
        return list(result.scalars().all())

    async def update(self, asset: Asset, **fields) -> Asset:
        for key, value in fields.items():
            if value is not None:
                setattr(asset, key, value)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset


class DepreciationRunRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> DepreciationRun:
        run = DepreciationRun(**fields)
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def get_by_id(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> DepreciationRun | None:
        result = await self.db.execute(
            select(DepreciationRun).where(
                DepreciationRun.id == run_id, DepreciationRun.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_period(
        self, organization_id: uuid.UUID, period_year: int, period_month: int
    ) -> DepreciationRun | None:
        result = await self.db.execute(
            select(DepreciationRun).where(
                DepreciationRun.organization_id == organization_id,
                DepreciationRun.period_year == period_year,
                DepreciationRun.period_month == period_month,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: DepreciationRunStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[DepreciationRun], int]:
        conditions = [DepreciationRun.organization_id == organization_id]
        if status is not None:
            conditions.append(DepreciationRun.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(DepreciationRun).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(DepreciationRun)
            .where(*conditions)
            .order_by(DepreciationRun.period_year.desc(), DepreciationRun.period_month.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, run: DepreciationRun, **fields) -> DepreciationRun:
        for key, value in fields.items():
            if value is not None:
                setattr(run, key, value)
        await self.db.flush()
        await self.db.refresh(run)
        return run


class DepreciationEntryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> DepreciationEntry:
        entry = DepreciationEntry(**fields)
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def list_for_run(self, depreciation_run_id: uuid.UUID) -> list[DepreciationEntry]:
        result = await self.db.execute(
            select(DepreciationEntry).where(DepreciationEntry.depreciation_run_id == depreciation_run_id)
        )
        return list(result.scalars().all())

    async def list_for_asset(self, asset_id: uuid.UUID) -> list[DepreciationEntry]:
        result = await self.db.execute(
            select(DepreciationEntry)
            .where(DepreciationEntry.asset_id == asset_id)
            .order_by(DepreciationEntry.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_latest_for_asset(self, asset_id: uuid.UUID) -> DepreciationEntry | None:
        result = await self.db.execute(
            select(DepreciationEntry)
            .where(DepreciationEntry.asset_id == asset_id)
            .order_by(DepreciationEntry.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def sum_posted_for_asset(
        self, asset_id: uuid.UUID, up_to_year: int | None = None, up_to_month: int | None = None
    ) -> float:
        conditions = [
            DepreciationEntry.asset_id == asset_id,
            DepreciationRun.status == DepreciationRunStatus.POSTED,
        ]
        if up_to_year is not None and up_to_month is not None:
            conditions.append(
                (DepreciationRun.period_year < up_to_year)
                | (
                    (DepreciationRun.period_year == up_to_year)
                    & (DepreciationRun.period_month <= up_to_month)
                )
            )
        result = await self.db.execute(
            select(func.coalesce(func.sum(DepreciationEntry.depreciation_amount), 0))
            .select_from(DepreciationEntry)
            .join(DepreciationRun, DepreciationRun.id == DepreciationEntry.depreciation_run_id)
            .where(*conditions)
        )
        return float(result.scalar_one())
