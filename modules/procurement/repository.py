import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.procurement.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderStatus,
)


class PurchaseOrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lines: list[dict], **fields) -> PurchaseOrder:
        po = PurchaseOrder(**fields)
        self.db.add(po)
        await self.db.flush()
        for line in lines:
            self.db.add(PurchaseOrderLine(purchase_order_id=po.id, **line))
        await self.db.flush()
        return await self.get_by_id(po.id, po.organization_id)

    async def replace_lines(self, po: PurchaseOrder, lines: list[dict]) -> None:
        for line in list(po.lines):
            await self.db.delete(line)
        await self.db.flush()
        for line in lines:
            self.db.add(PurchaseOrderLine(purchase_order_id=po.id, **line))
        await self.db.flush()

    async def get_by_id(self, po_id: uuid.UUID, organization_id: uuid.UUID) -> PurchaseOrder | None:
        result = await self.db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id, PurchaseOrder.organization_id == organization_id)
            .options(selectinload(PurchaseOrder.lines))
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, po_number: str) -> PurchaseOrder | None:
        result = await self.db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.organization_id == organization_id, PurchaseOrder.po_number == po_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID | None = None,
        status: PurchaseOrderStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PurchaseOrder], int]:
        conditions = [PurchaseOrder.organization_id == organization_id]
        if vendor_id is not None:
            conditions.append(PurchaseOrder.vendor_id == vendor_id)
        if status is not None:
            conditions.append(PurchaseOrder.status == status)
        if date_from is not None:
            conditions.append(PurchaseOrder.order_date >= date_from)
        if date_to is not None:
            conditions.append(PurchaseOrder.order_date <= date_to)

        count_result = await self.db.execute(select(func.count()).select_from(PurchaseOrder).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(PurchaseOrder)
            .where(*conditions)
            .options(selectinload(PurchaseOrder.lines))
            .order_by(PurchaseOrder.order_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), total

    async def update(self, po: PurchaseOrder, **fields) -> PurchaseOrder:
        for key, value in fields.items():
            if value is not None:
                setattr(po, key, value)
        await self.db.flush()
        await self.db.refresh(po)
        return po

    async def get_line_by_id(self, line_id: uuid.UUID) -> PurchaseOrderLine | None:
        result = await self.db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.id == line_id))
        return result.scalar_one_or_none()

    async def update_line(self, line: PurchaseOrderLine, **fields) -> PurchaseOrderLine:
        for key, value in fields.items():
            if value is not None:
                setattr(line, key, value)
        await self.db.flush()
        await self.db.refresh(line)
        return line


class GoodsReceiptRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lines: list[dict], **fields) -> GoodsReceipt:
        receipt = GoodsReceipt(**fields)
        self.db.add(receipt)
        await self.db.flush()
        for line in lines:
            self.db.add(GoodsReceiptLine(goods_receipt_id=receipt.id, **line))
        await self.db.flush()
        return await self.get_by_id(receipt.id, receipt.organization_id)

    async def get_by_id(self, receipt_id: uuid.UUID, organization_id: uuid.UUID) -> GoodsReceipt | None:
        result = await self.db.execute(
            select(GoodsReceipt)
            .where(GoodsReceipt.id == receipt_id, GoodsReceipt.organization_id == organization_id)
            .options(selectinload(GoodsReceipt.lines))
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, organization_id: uuid.UUID, receipt_number: str) -> GoodsReceipt | None:
        result = await self.db.execute(
            select(GoodsReceipt).where(
                GoodsReceipt.organization_id == organization_id, GoodsReceipt.receipt_number == receipt_number
            )
        )
        return result.scalar_one_or_none()

    async def list_for_purchase_order(self, purchase_order_id: uuid.UUID) -> list[GoodsReceipt]:
        result = await self.db.execute(
            select(GoodsReceipt)
            .where(GoodsReceipt.purchase_order_id == purchase_order_id)
            .options(selectinload(GoodsReceipt.lines))
            .order_by(GoodsReceipt.receipt_date.desc())
        )
        return list(result.scalars().unique().all())
