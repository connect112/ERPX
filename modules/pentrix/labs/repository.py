import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.labs.models import Lab


class LabRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Lab:
        lab = Lab(**fields)
        self.db.add(lab)
        await self.db.flush()
        await self.db.refresh(lab)
        return lab

    async def get_by_id(self, lab_id: uuid.UUID, organization_id: uuid.UUID) -> Lab | None:
        result = await self.db.execute(
            select(Lab).where(Lab.id == lab_id, Lab.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, organization_id: uuid.UUID, slug: str) -> Lab | None:
        result = await self.db.execute(
            select(Lab).where(Lab.organization_id == organization_id, Lab.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Lab]:
        result = await self.db.execute(select(Lab).where(Lab.organization_id == organization_id))
        return list(result.scalars().all())

    async def update(self, lab: Lab, **fields) -> Lab:
        for key, value in fields.items():
            if value is not None:
                setattr(lab, key, value)
        await self.db.flush()
        await self.db.refresh(lab)
        return lab

    async def delete(self, lab: Lab) -> None:
        await self.db.delete(lab)
        await self.db.flush()
