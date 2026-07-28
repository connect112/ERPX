import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.categories.models import Category


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Category:
        category = Category(**fields)
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def get_by_id(self, category_id: uuid.UUID, organization_id: uuid.UUID) -> Category | None:
        result = await self.db.execute(
            select(Category).where(
                Category.id == category_id, Category.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, organization_id: uuid.UUID, slug: str) -> Category | None:
        result = await self.db.execute(
            select(Category).where(Category.organization_id == organization_id, Category.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Category]:
        result = await self.db.execute(
            select(Category).where(Category.organization_id == organization_id).order_by(Category.name)
        )
        return list(result.scalars().all())

    async def update(self, category: Category, **fields) -> Category:
        for key, value in fields.items():
            if value is not None:
                setattr(category, key, value)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def delete(self, category: Category) -> None:
        await self.db.delete(category)
        await self.db.flush()
