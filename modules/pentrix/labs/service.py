import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.pentrix.labs.models import Lab
from modules.pentrix.labs.repository import LabRepository

logger = get_logger(__name__)


class LabService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LabRepository(db)

    async def create_lab(self, organization_id: uuid.UUID, slug: str, **fields) -> Lab:
        existing = await self.repo.get_by_slug(organization_id, slug)
        if existing:
            raise ConflictError(f"A lab with slug '{slug}' already exists.")
        lab = await self.repo.create(organization_id=organization_id, slug=slug, **fields)
        logger.info("lab_created", lab_id=str(lab.id))
        return lab

    async def get_lab(self, lab_id: uuid.UUID, organization_id: uuid.UUID) -> Lab:
        lab = await self.repo.get_by_id(lab_id, organization_id)
        if not lab:
            raise NotFoundError("Lab", lab_id)
        return lab

    async def list_labs(self, organization_id: uuid.UUID) -> list[Lab]:
        return await self.repo.list_for_organization(organization_id)

    async def update_lab(self, lab_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Lab:
        lab = await self.get_lab(lab_id, organization_id)
        updated = await self.repo.update(lab, **fields)
        logger.info("lab_updated", lab_id=str(lab_id))
        return updated

    async def delete_lab(self, lab_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        lab = await self.get_lab(lab_id, organization_id)
        await self.repo.delete(lab)
        logger.info("lab_deleted", lab_id=str(lab_id))
