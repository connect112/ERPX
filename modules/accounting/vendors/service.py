import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.accounting.vendors.models import Vendor
from modules.accounting.vendors.repository import VendorRepository

logger = get_logger(__name__)


class VendorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = VendorRepository(db)

    async def create_vendor(self, organization_id: uuid.UUID, vendor_code: str, **fields) -> Vendor:
        existing = await self.repo.get_by_code(organization_id, vendor_code)
        if existing:
            raise ConflictError(f"A vendor with code '{vendor_code}' already exists.")
        vendor = await self.repo.create(organization_id=organization_id, vendor_code=vendor_code, **fields)
        logger.info("vendor_created", vendor_id=str(vendor.id))
        return vendor

    async def get_vendor(self, vendor_id: uuid.UUID, organization_id: uuid.UUID) -> Vendor:
        vendor = await self.repo.get_by_id(vendor_id, organization_id)
        if not vendor:
            raise NotFoundError("Vendor", vendor_id)
        return vendor

    async def list_vendors(self, organization_id: uuid.UUID, **filters) -> tuple[list[Vendor], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_vendor(self, vendor_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Vendor:
        vendor = await self.get_vendor(vendor_id, organization_id)
        updated = await self.repo.update(vendor, **fields)
        logger.info("vendor_updated", vendor_id=str(vendor_id))
        return updated

    async def delete_vendor(self, vendor_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        vendor = await self.get_vendor(vendor_id, organization_id)
        await self.repo.soft_delete(vendor)
        logger.info("vendor_deleted", vendor_id=str(vendor_id))
