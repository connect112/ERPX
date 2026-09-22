import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.organizations.models import Organization
from modules.organizations.repository import OrganizationRepository
from modules.settings.service import SettingsService

logger = get_logger(__name__)

# The bootstrap organization apps/api/scripts/seed.py creates purely to
# give the SEED_SUPERADMIN account a profile/organization_id to resolve
# (see get_current_user_organization_id) — it holds no real customer data
# and was never meant to be a selectable tenant. Without this filter it
# shows up as a second, confusing entry in Super Admin's Organizations
# list alongside actual customer organizations.
SYSTEM_ORG_SLUG = "erpx-system"


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = OrganizationRepository(db)

    async def create_organization(self, **fields) -> Organization:
        existing = await self.repo.get_by_slug(fields["slug"])
        if existing:
            raise ConflictError(f"An organization with slug '{fields['slug']}' already exists.")
        org = await self.repo.create(**fields)
        await SettingsService(self.db).seed_defaults_for_organization(org.id)
        logger.info("organization_created", org_id=str(org.id), slug=org.slug)
        return org

    async def get_organization(self, org_id: uuid.UUID) -> Organization:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization", org_id)
        return org

    async def list_organizations(self, skip: int, limit: int) -> list[Organization]:
        return await self.repo.list_all(skip, limit, exclude_slug=SYSTEM_ORG_SLUG)

    async def update_organization(self, org_id: uuid.UUID, **fields) -> Organization:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization", org_id)
        updated = await self.repo.update(org, **fields)
        logger.info("organization_updated", org_id=str(org_id))
        return updated

    async def delete_organization(self, org_id: uuid.UUID) -> None:
        org = await self.repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("Organization", org_id)
        await self.repo.soft_delete(org)
        logger.info("organization_deleted", org_id=str(org_id))
