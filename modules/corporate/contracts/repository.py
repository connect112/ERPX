import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.corporate.contracts.models import Contract, ContractStatus


class ContractRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Contract:
        contract = Contract(**fields)
        self.db.add(contract)
        await self.db.flush()
        await self.db.refresh(contract)
        return contract

    async def get_by_id(self, contract_id: uuid.UUID, organization_id: uuid.UUID) -> Contract | None:
        result = await self.db.execute(
            select(Contract).where(Contract.id == contract_id, Contract.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, contract_number: str) -> Contract | None:
        result = await self.db.execute(
            select(Contract).where(
                Contract.organization_id == organization_id, Contract.contract_number == contract_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        status: ContractStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Contract], int]:
        conditions = [Contract.organization_id == organization_id]
        if client_id is not None:
            conditions.append(Contract.client_id == client_id)
        if status is not None:
            conditions.append(Contract.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(Contract).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Contract).where(*conditions).order_by(Contract.start_date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_expiring(self, organization_id: uuid.UUID, within_days: int) -> list[Contract]:
        from datetime import date, timedelta

        cutoff = date.today() + timedelta(days=within_days)
        result = await self.db.execute(
            select(Contract).where(
                Contract.organization_id == organization_id,
                Contract.status == ContractStatus.ACTIVE,
                Contract.end_date.is_not(None),
                Contract.end_date <= cutoff,
            )
        )
        return list(result.scalars().all())

    async def update(self, contract: Contract, **fields) -> Contract:
        for key, value in fields.items():
            if value is not None:
                setattr(contract, key, value)
        await self.db.flush()
        await self.db.refresh(contract)
        return contract
