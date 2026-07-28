import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.settings.models import OrganizationSetting


class SettingsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, organization_id: uuid.UUID, key: str) -> OrganizationSetting | None:
        result = await self.db.execute(
            select(OrganizationSetting).where(
                OrganizationSetting.organization_id == organization_id,
                OrganizationSetting.key == key,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[OrganizationSetting]:
        result = await self.db.execute(
            select(OrganizationSetting)
            .where(OrganizationSetting.organization_id == organization_id)
            .order_by(OrganizationSetting.key)
        )
        return list(result.scalars().all())

    async def upsert(self, organization_id: uuid.UUID, key: str, value: str) -> OrganizationSetting:
        existing = await self.get(organization_id, key)
        if existing:
            existing.value = value
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        setting = OrganizationSetting(organization_id=organization_id, key=key, value=value)
        self.db.add(setting)
        await self.db.flush()
        await self.db.refresh(setting)
        return setting
