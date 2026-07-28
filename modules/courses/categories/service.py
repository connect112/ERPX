import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.courses.categories.models import Category
from modules.courses.categories.repository import CategoryRepository

logger = get_logger(__name__)


class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CategoryRepository(db)

    async def create_category(self, organization_id: uuid.UUID, slug: str, **fields) -> Category:
        existing = await self.repo.get_by_slug(organization_id, slug)
        if existing:
            raise ConflictError(f"A category with slug '{slug}' already exists.")
        category = await self.repo.create(organization_id=organization_id, slug=slug, **fields)
        logger.info("category_created", category_id=str(category.id))
        return category

    async def get_category(self, category_id: uuid.UUID, organization_id: uuid.UUID) -> Category:
        category = await self.repo.get_by_id(category_id, organization_id)
        if not category:
            raise NotFoundError("Category", category_id)
        return category

    async def list_categories(self, organization_id: uuid.UUID) -> list[Category]:
        return await self.repo.list_for_organization(organization_id)

    async def update_category(
        self, category_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Category:
        category = await self.get_category(category_id, organization_id)
        updated = await self.repo.update(category, **fields)
        logger.info("category_updated", category_id=str(category_id))
        return updated

    async def delete_category(self, category_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        category = await self.get_category(category_id, organization_id)
        await self.repo.delete(category)
        logger.info("category_deleted", category_id=str(category_id))
