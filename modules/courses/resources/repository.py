import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.resources.models import Resource


class ResourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Resource:
        resource = Resource(**fields)
        self.db.add(resource)
        await self.db.flush()
        await self.db.refresh(resource)
        return resource

    async def get_by_id(self, resource_id: uuid.UUID) -> Resource | None:
        result = await self.db.execute(select(Resource).where(Resource.id == resource_id))
        return result.scalar_one_or_none()

    async def list_for_lesson(self, lesson_id: uuid.UUID) -> list[Resource]:
        result = await self.db.execute(
            select(Resource).where(Resource.lesson_id == lesson_id).order_by(Resource.created_at)
        )
        return list(result.scalars().all())

    async def update(self, resource: Resource, **fields) -> Resource:
        for key, value in fields.items():
            if value is not None:
                setattr(resource, key, value)
        await self.db.flush()
        await self.db.refresh(resource)
        return resource

    async def delete(self, resource: Resource) -> None:
        await self.db.delete(resource)
        await self.db.flush()
