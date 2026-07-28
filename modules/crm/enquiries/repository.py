import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.crm.enquiries.models import Enquiry


class EnquiryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Enquiry:
        enquiry = Enquiry(**fields)
        self.db.add(enquiry)
        await self.db.flush()
        await self.db.refresh(enquiry)
        return enquiry

    async def get_by_id(self, enquiry_id: uuid.UUID) -> Enquiry | None:
        result = await self.db.execute(select(Enquiry).where(Enquiry.id == enquiry_id))
        return result.scalar_one_or_none()

    async def list_for_lead(self, lead_id: uuid.UUID) -> list[Enquiry]:
        result = await self.db.execute(
            select(Enquiry).where(Enquiry.lead_id == lead_id).order_by(Enquiry.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, enquiry: Enquiry, **fields) -> Enquiry:
        for key, value in fields.items():
            if value is not None:
                setattr(enquiry, key, value)
        await self.db.flush()
        await self.db.refresh(enquiry)
        return enquiry

    async def delete(self, enquiry: Enquiry) -> None:
        await self.db.delete(enquiry)
        await self.db.flush()
