import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from modules.settings.models import OrganizationSetting
from modules.settings.repository import SettingsRepository
from modules.settings.schemas import DEFAULT_ORGANIZATION_SETTINGS

logger = get_logger(__name__)


class SettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SettingsRepository(db)

    async def seed_defaults_for_organization(self, organization_id: uuid.UUID) -> None:
        for key, value in DEFAULT_ORGANIZATION_SETTINGS.items():
            existing = await self.repo.get(organization_id, key)
            if not existing:
                await self.repo.upsert(organization_id, key, value)
        logger.info("organization_settings_seeded", org_id=str(organization_id))

    async def get_setting(self, organization_id: uuid.UUID, key: str) -> str | None:
        setting = await self.repo.get(organization_id, key)
        return setting.value if setting else DEFAULT_ORGANIZATION_SETTINGS.get(key)

    async def list_settings(self, organization_id: uuid.UUID) -> list[OrganizationSetting]:
        return await self.repo.list_for_organization(organization_id)

    async def upsert_setting(self, organization_id: uuid.UUID, key: str, value: str) -> OrganizationSetting:
        setting = await self.repo.upsert(organization_id, key, value)
        logger.info("organization_setting_updated", org_id=str(organization_id), key=key)
        return setting
