import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.crm.admissions.models import Admission


class AdmissionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Admission:
        admission = Admission(**fields)
        self.db.add(admission)
        await self.db.flush()
        await self.db.refresh(admission)
        return admission

    async def get_by_id(self, admission_id: uuid.UUID, organization_id: uuid.UUID) -> Admission | None:
        result = await self.db.execute(
            select(Admission).where(
                Admission.id == admission_id, Admission.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_lead_id(self, lead_id: uuid.UUID) -> Admission | None:
        result = await self.db.execute(select(Admission).where(Admission.lead_id == lead_id))
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Admission]:
        result = await self.db.execute(
            select(Admission)
            .where(Admission.organization_id == organization_id)
            .order_by(Admission.admission_date.desc())
        )
        return list(result.scalars().all())

    async def update(self, admission: Admission, **fields) -> Admission:
        for key, value in fields.items():
            if value is not None:
                setattr(admission, key, value)
        await self.db.flush()
        await self.db.refresh(admission)
        return admission
