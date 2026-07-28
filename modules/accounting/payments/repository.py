import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.payments.models import Payment, PaymentStatus


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Payment:
        payment = Payment(**fields)
        self.db.add(payment)
        await self.db.flush()
        await self.db.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: uuid.UUID, organization_id: uuid.UUID) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, payment_number: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(
                Payment.organization_id == organization_id, Payment.payment_number == payment_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID | None = None,
        expense_id: uuid.UUID | None = None,
        status: PaymentStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Payment], int]:
        conditions = [Payment.organization_id == organization_id]
        if vendor_id is not None:
            conditions.append(Payment.vendor_id == vendor_id)
        if expense_id is not None:
            conditions.append(Payment.expense_id == expense_id)
        if status is not None:
            conditions.append(Payment.status == status)
        if date_from is not None:
            conditions.append(Payment.payment_date >= date_from)
        if date_to is not None:
            conditions.append(Payment.payment_date <= date_to)

        count_result = await self.db.execute(select(func.count()).select_from(Payment).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Payment).where(*conditions).order_by(Payment.payment_date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, payment: Payment, **fields) -> Payment:
        for key, value in fields.items():
            if value is not None:
                setattr(payment, key, value)
        await self.db.flush()
        await self.db.refresh(payment)
        return payment
