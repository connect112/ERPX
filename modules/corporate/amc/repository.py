import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.corporate.amc.models import AMCContract, AMCStatus, AMCVisit, AMCVisitStatus


class AMCContractRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AMCContract:
        contract = AMCContract(**fields)
        self.db.add(contract)
        await self.db.flush()
        await self.db.refresh(contract)
        return contract

    async def get_by_id(self, amc_contract_id: uuid.UUID, organization_id: uuid.UUID) -> AMCContract | None:
        result = await self.db.execute(
            select(AMCContract).where(
                AMCContract.id == amc_contract_id, AMCContract.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, amc_number: str) -> AMCContract | None:
        result = await self.db.execute(
            select(AMCContract).where(
                AMCContract.organization_id == organization_id, AMCContract.amc_number == amc_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        status: AMCStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AMCContract], int]:
        conditions = [AMCContract.organization_id == organization_id]
        if client_id is not None:
            conditions.append(AMCContract.client_id == client_id)
        if status is not None:
            conditions.append(AMCContract.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(AMCContract).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(AMCContract).where(*conditions).order_by(AMCContract.end_date.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_due_for_renewal(self, organization_id: uuid.UUID) -> list[AMCContract]:
        """
        `renewal_reminder_days` varies per row, so the "due soon" window
        isn't expressible as a single SQL comparison against a shared
        cutoff — active contracts are fetched and filtered in Python instead.
        """
        today = date.today()
        result = await self.db.execute(
            select(AMCContract).where(
                AMCContract.organization_id == organization_id, AMCContract.status == AMCStatus.ACTIVE
            )
        )
        contracts = result.scalars().all()
        return [c for c in contracts if c.end_date <= today + timedelta(days=c.renewal_reminder_days)]

    async def update(self, contract: AMCContract, **fields) -> AMCContract:
        for key, value in fields.items():
            if value is not None:
                setattr(contract, key, value)
        await self.db.flush()
        await self.db.refresh(contract)
        return contract


class AMCVisitRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AMCVisit:
        visit = AMCVisit(**fields)
        self.db.add(visit)
        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def get_by_id(self, visit_id: uuid.UUID) -> AMCVisit | None:
        result = await self.db.execute(select(AMCVisit).where(AMCVisit.id == visit_id))
        return result.scalar_one_or_none()

    async def list_for_contract(
        self, amc_contract_id: uuid.UUID, status: AMCVisitStatus | None = None
    ) -> list[AMCVisit]:
        conditions = [AMCVisit.amc_contract_id == amc_contract_id]
        if status is not None:
            conditions.append(AMCVisit.status == status)
        result = await self.db.execute(select(AMCVisit).where(*conditions).order_by(AMCVisit.visit_date.desc()))
        return list(result.scalars().all())

    async def update(self, visit: AMCVisit, **fields) -> AMCVisit:
        for key, value in fields.items():
            if value is not None:
                setattr(visit, key, value)
        await self.db.flush()
        await self.db.refresh(visit)
        return visit
