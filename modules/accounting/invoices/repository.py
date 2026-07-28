import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.accounting.invoices.models import Invoice, InvoiceLine, InvoiceStatus


class InvoiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lines: list[dict], **fields) -> Invoice:
        invoice = Invoice(**fields)
        self.db.add(invoice)
        await self.db.flush()
        for index, line in enumerate(lines):
            self.db.add(InvoiceLine(invoice_id=invoice.id, line_order=index, **line))
        await self.db.flush()
        return await self.get_by_id(invoice.id, invoice.organization_id)

    async def replace_lines(self, invoice: Invoice, lines: list[dict]) -> None:
        for line in list(invoice.lines):
            await self.db.delete(line)
        await self.db.flush()
        for index, line in enumerate(lines):
            self.db.add(InvoiceLine(invoice_id=invoice.id, line_order=index, **line))
        await self.db.flush()

    async def get_by_id(self, invoice_id: uuid.UUID, organization_id: uuid.UUID) -> Invoice | None:
        result = await self.db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.organization_id == organization_id)
            .options(selectinload(Invoice.lines))
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, invoice_number: str) -> Invoice | None:
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.organization_id == organization_id, Invoice.invoice_number == invoice_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        status: InvoiceStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Invoice], int]:
        conditions = [Invoice.organization_id == organization_id]
        if customer_id is not None:
            conditions.append(Invoice.customer_id == customer_id)
        if status is not None:
            conditions.append(Invoice.status == status)
        if date_from is not None:
            conditions.append(Invoice.invoice_date >= date_from)
        if date_to is not None:
            conditions.append(Invoice.invoice_date <= date_to)

        count_result = await self.db.execute(select(func.count()).select_from(Invoice).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Invoice)
            .where(*conditions)
            .options(selectinload(Invoice.lines))
            .order_by(Invoice.invoice_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), total

    async def list_outstanding_for_customer(self, customer_id: uuid.UUID) -> list[Invoice]:
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.customer_id == customer_id,
                Invoice.status.in_(
                    [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]
                ),
            )
        )
        return list(result.scalars().all())

    async def list_all_outstanding(self, organization_id: uuid.UUID) -> list[Invoice]:
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.organization_id == organization_id,
                Invoice.status.in_(
                    [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]
                ),
            )
        )
        return list(result.scalars().all())

    async def update(self, invoice: Invoice, **fields) -> Invoice:
        for key, value in fields.items():
            if value is not None:
                setattr(invoice, key, value)
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def count_for_organization(self, organization_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Invoice).where(Invoice.organization_id == organization_id)
        )
        return result.scalar_one()
