import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.vendors.models import Vendor


class VendorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Vendor:
        vendor = Vendor(**fields)
        self.db.add(vendor)
        await self.db.flush()
        await self.db.refresh(vendor)
        return vendor

    async def get_by_id(self, vendor_id: uuid.UUID, organization_id: uuid.UUID) -> Vendor | None:
        result = await self.db.execute(
            select(Vendor).where(
                Vendor.id == vendor_id,
                Vendor.organization_id == organization_id,
                Vendor.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, vendor_code: str) -> Vendor | None:
        result = await self.db.execute(
            select(Vendor).where(
                Vendor.organization_id == organization_id, Vendor.vendor_code == vendor_code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Vendor], int]:
        conditions = [Vendor.organization_id == organization_id, Vendor.deleted_at.is_(None)]
        if is_active is not None:
            conditions.append(Vendor.is_active == is_active)
        if search:
            like_pattern = f"%{search}%"
            conditions.append(
                (Vendor.name.ilike(like_pattern))
                | (Vendor.vendor_code.ilike(like_pattern))
                | (Vendor.email.ilike(like_pattern))
            )

        count_result = await self.db.execute(select(func.count()).select_from(Vendor).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Vendor).where(*conditions).order_by(Vendor.name.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, vendor: Vendor, **fields) -> Vendor:
        for key, value in fields.items():
            if value is not None:
                setattr(vendor, key, value)
        await self.db.flush()
        await self.db.refresh(vendor)
        return vendor

    async def soft_delete(self, vendor: Vendor) -> None:
        from datetime import datetime, timezone

        vendor.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
