import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.expense_claims.models import ExpenseClaim, ExpenseClaimStatus


class ExpenseClaimRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ExpenseClaim:
        claim = ExpenseClaim(**fields)
        self.db.add(claim)
        await self.db.flush()
        await self.db.refresh(claim)
        return claim

    async def get_by_id(self, claim_id: uuid.UUID, organization_id: uuid.UUID) -> ExpenseClaim | None:
        result = await self.db.execute(
            select(ExpenseClaim).where(
                ExpenseClaim.id == claim_id, ExpenseClaim.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_employee(
        self,
        employee_id: uuid.UUID,
        status: ExpenseClaimStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ExpenseClaim], int]:
        conditions = [ExpenseClaim.employee_id == employee_id]
        if status is not None:
            conditions.append(ExpenseClaim.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(ExpenseClaim).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(ExpenseClaim).where(*conditions).order_by(ExpenseClaim.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: ExpenseClaimStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ExpenseClaim], int]:
        conditions = [ExpenseClaim.organization_id == organization_id]
        if status is not None:
            conditions.append(ExpenseClaim.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(ExpenseClaim).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(ExpenseClaim).where(*conditions).order_by(ExpenseClaim.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_approved_unapplied_for_period(
        self, organization_id: uuid.UUID, employee_id: uuid.UUID, period_year: int, period_month: int
    ) -> list[ExpenseClaim]:
        result = await self.db.execute(
            select(ExpenseClaim).where(
                ExpenseClaim.organization_id == organization_id,
                ExpenseClaim.employee_id == employee_id,
                ExpenseClaim.period_year == period_year,
                ExpenseClaim.period_month == period_month,
                ExpenseClaim.status == ExpenseClaimStatus.APPROVED,
                ExpenseClaim.applied_payroll_run_id.is_(None),
            )
        )
        return list(result.scalars().all())

    async def update(self, claim: ExpenseClaim, **fields) -> ExpenseClaim:
        for key, value in fields.items():
            if value is not None:
                setattr(claim, key, value)
        await self.db.flush()
        await self.db.refresh(claim)
        return claim
