import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.organizations.models import Organization


class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Organization:
        org = Organization(**fields)
        self.db.add(org)
        await self.db.flush()
        await self.db.refresh(org)
        return org

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.slug == slug, Organization.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 50) -> list[Organization]:
        result = await self.db.execute(
            select(Organization)
            .where(Organization.deleted_at.is_(None))
            .order_by(Organization.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, org: Organization, **fields) -> Organization:
        for key, value in fields.items():
            if value is not None:
                setattr(org, key, value)
        await self.db.flush()
        return org

    async def soft_delete(self, org: Organization) -> None:
        from datetime import datetime, timezone

        org.deleted_at = datetime.now(timezone.utc)
        org.is_active = False
        await self.db.flush()
