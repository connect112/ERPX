import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.gst.models import GSTRate


class GSTRateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> GSTRate:
        rate = GSTRate(**fields)
        self.db.add(rate)
        await self.db.flush()
        await self.db.refresh(rate)
        return rate

    async def get_by_id(self, rate_id: uuid.UUID, organization_id: uuid.UUID) -> GSTRate | None:
        result = await self.db.execute(
            select(GSTRate).where(GSTRate.id == rate_id, GSTRate.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, organization_id: uuid.UUID, name: str) -> GSTRate | None:
        result = await self.db.execute(
            select(GSTRate).where(GSTRate.organization_id == organization_id, GSTRate.name == name)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[GSTRate]:
        conditions = [GSTRate.organization_id == organization_id]
        if is_active is not None:
            conditions.append(GSTRate.is_active == is_active)
        result = await self.db.execute(select(GSTRate).where(*conditions).order_by(GSTRate.rate_percent.asc()))
        return list(result.scalars().all())

    async def update(self, rate: GSTRate, **fields) -> GSTRate:
        for key, value in fields.items():
            if value is not None:
                setattr(rate, key, value)
        await self.db.flush()
        await self.db.refresh(rate)
        return rate
