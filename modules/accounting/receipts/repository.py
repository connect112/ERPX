import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.receipts.models import Receipt, ReceiptStatus


class ReceiptRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Receipt:
        receipt = Receipt(**fields)
        self.db.add(receipt)
        await self.db.flush()
        await self.db.refresh(receipt)
        return receipt

    async def get_by_id(self, receipt_id: uuid.UUID, organization_id: uuid.UUID) -> Receipt | None:
        result = await self.db.execute(
            select(Receipt).where(Receipt.id == receipt_id, Receipt.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, receipt_number: str) -> Receipt | None:
        result = await self.db.execute(
            select(Receipt).where(
                Receipt.organization_id == organization_id, Receipt.receipt_number == receipt_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
        status: ReceiptStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Receipt], int]:
        conditions = [Receipt.organization_id == organization_id]
        if customer_id is not None:
            conditions.append(Receipt.customer_id == customer_id)
        if invoice_id is not None:
            conditions.append(Receipt.invoice_id == invoice_id)
        if status is not None:
            conditions.append(Receipt.status == status)
        if date_from is not None:
            conditions.append(Receipt.receipt_date >= date_from)
        if date_to is not None:
            conditions.append(Receipt.receipt_date <= date_to)

        count_result = await self.db.execute(select(func.count()).select_from(Receipt).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Receipt).where(*conditions).order_by(Receipt.receipt_date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, receipt: Receipt, **fields) -> Receipt:
        for key, value in fields.items():
            if value is not None:
                setattr(receipt, key, value)
        await self.db.flush()
        await self.db.refresh(receipt)
        return receipt
