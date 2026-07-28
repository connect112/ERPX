import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.integrations.models import Integration


class IntegrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Integration:
        integration = Integration(**fields)
        self.db.add(integration)
        await self.db.flush()
        await self.db.refresh(integration)
        return integration

    async def get_by_id(self, integration_id: uuid.UUID, organization_id: uuid.UUID) -> Integration | None:
        result = await self.db.execute(
            select(Integration).where(
                Integration.id == integration_id, Integration.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Integration], int]:
        conditions = [Integration.organization_id == organization_id]
        count_result = await self.db.execute(
            select(func.count()).select_from(Integration).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Integration)
            .where(*conditions)
            .order_by(Integration.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, integration: Integration, **fields) -> Integration:
        for key, value in fields.items():
            if value is not None:
                setattr(integration, key, value)
        await self.db.flush()
        await self.db.refresh(integration)
        return integration

    async def delete(self, integration: Integration) -> None:
        await self.db.delete(integration)
        await self.db.flush()
