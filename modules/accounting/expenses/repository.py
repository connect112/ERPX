import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.expenses.models import Expense, ExpenseStatus


class ExpenseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Expense:
        expense = Expense(**fields)
        self.db.add(expense)
        await self.db.flush()
        await self.db.refresh(expense)
        return expense

    async def get_by_id(self, expense_id: uuid.UUID, organization_id: uuid.UUID) -> Expense | None:
        result = await self.db.execute(
            select(Expense).where(Expense.id == expense_id, Expense.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, expense_number: str) -> Expense | None:
        result = await self.db.execute(
            select(Expense).where(
                Expense.organization_id == organization_id, Expense.expense_number == expense_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID | None = None,
        status: ExpenseStatus | None = None,
        category: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Expense], int]:
        conditions = [Expense.organization_id == organization_id]
        if vendor_id is not None:
            conditions.append(Expense.vendor_id == vendor_id)
        if status is not None:
            conditions.append(Expense.status == status)
        if category is not None:
            conditions.append(Expense.category == category)
        if date_from is not None:
            conditions.append(Expense.expense_date >= date_from)
        if date_to is not None:
            conditions.append(Expense.expense_date <= date_to)

        count_result = await self.db.execute(select(func.count()).select_from(Expense).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Expense).where(*conditions).order_by(Expense.expense_date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_all_outstanding(self, organization_id: uuid.UUID) -> list[Expense]:
        result = await self.db.execute(
            select(Expense).where(
                Expense.organization_id == organization_id,
                Expense.status.in_([ExpenseStatus.APPROVED, ExpenseStatus.PARTIALLY_PAID]),
            )
        )
        return list(result.scalars().all())

    async def update(self, expense: Expense, **fields) -> Expense:
        for key, value in fields.items():
            if value is not None:
                setattr(expense, key, value)
        await self.db.flush()
        await self.db.refresh(expense)
        return expense
