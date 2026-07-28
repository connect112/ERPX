import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.gst.service import GSTService
from modules.accounting.vendors.repository import VendorRepository
from modules.inventory.repository import InventoryItemRepository, WarehouseRepository
from modules.inventory.service import StockService
from modules.procurement.models import GoodsReceipt, PurchaseOrder, PurchaseOrderStatus
from modules.procurement.repository import GoodsReceiptRepository, PurchaseOrderRepository

logger = get_logger(__name__)

_EDITABLE_STATUSES = {PurchaseOrderStatus.DRAFT}
_RECEIVABLE_STATUSES = {PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTIALLY_RECEIVED}


async def _build_lines(gst_service: GSTService, organization_id: uuid.UUID, raw_lines: list[dict]) -> list[dict]:
    computed = []
    for line in raw_lines:
        line_subtotal = round(float(line["quantity_ordered"]) * float(line["unit_price"]), 2)
        tax_amount = 0.0
        if line.get("gst_rate_id") is not None:
            tax_result = await gst_service.compute_tax(
                organization_id, line_subtotal, line["gst_rate_id"], is_interstate=False
            )
            tax_amount = tax_result["total_tax"]
        computed.append(
            {
                "item_id": line["item_id"],
                "gst_rate_id": line.get("gst_rate_id"),
                "description": line["description"],
                "quantity_ordered": line["quantity_ordered"],
                "unit_price": line["unit_price"],
                "line_subtotal": line_subtotal,
                "tax_amount": tax_amount,
                "line_total": round(line_subtotal + tax_amount, 2),
            }
        )
    return computed


class PurchaseOrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PurchaseOrderRepository(db)
        self.vendor_repo = VendorRepository(db)
        self.item_repo = InventoryItemRepository(db)
        self.gst_service = GSTService(db)

    async def create_purchase_order(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID,
        po_number: str,
        lines: list[dict],
        created_by_user_id: uuid.UUID | None = None,
        **fields,
    ) -> PurchaseOrder:
        vendor = await self.vendor_repo.get_by_id(vendor_id, organization_id)
        if not vendor:
            raise NotFoundError("Vendor", vendor_id)

        existing = await self.repo.get_by_number(organization_id, po_number)
        if existing:
            raise ConflictError(f"A purchase order with number '{po_number}' already exists.")

        for line in lines:
            item = await self.item_repo.get_by_id(line["item_id"], organization_id)
            if not item:
                raise NotFoundError("Inventory item", line["item_id"])

        computed_lines = await _build_lines(self.gst_service, organization_id, lines)
        subtotal_amount = round(sum(l["line_subtotal"] for l in computed_lines), 2)
        tax_amount = round(sum(l["tax_amount"] for l in computed_lines), 2)

        po = await self.repo.create(
            lines=computed_lines,
            organization_id=organization_id,
            vendor_id=vendor_id,
            po_number=po_number,
            subtotal_amount=subtotal_amount,
            tax_amount=tax_amount,
            total_amount=round(subtotal_amount + tax_amount, 2),
            created_by_user_id=created_by_user_id,
            **fields,
        )
        logger.info("purchase_order_created", po_id=str(po.id), po_number=po_number)
        return po

    async def get_purchase_order(self, po_id: uuid.UUID, organization_id: uuid.UUID) -> PurchaseOrder:
        po = await self.repo.get_by_id(po_id, organization_id)
        if not po:
            raise NotFoundError("Purchase order", po_id)
        return po

    async def list_purchase_orders(self, organization_id: uuid.UUID, **filters) -> tuple[list[PurchaseOrder], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_purchase_order(
        self, po_id: uuid.UUID, organization_id: uuid.UUID, lines: list[dict] | None = None, **fields
    ) -> PurchaseOrder:
        po = await self.get_purchase_order(po_id, organization_id)
        if po.status not in _EDITABLE_STATUSES:
            raise ValidationError("Only draft purchase orders can be edited.")

        if lines is not None:
            for line in lines:
                item = await self.item_repo.get_by_id(line["item_id"], organization_id)
                if not item:
                    raise NotFoundError("Inventory item", line["item_id"])
            computed_lines = await _build_lines(self.gst_service, organization_id, lines)
            await self.repo.replace_lines(po, computed_lines)
            fields["subtotal_amount"] = round(sum(l["line_subtotal"] for l in computed_lines), 2)
            fields["tax_amount"] = round(sum(l["tax_amount"] for l in computed_lines), 2)
            fields["total_amount"] = round(fields["subtotal_amount"] + fields["tax_amount"], 2)

        updated = await self.repo.update(po, **fields)
        logger.info("purchase_order_updated", po_id=str(po_id))
        return updated

    async def send_purchase_order(self, po_id: uuid.UUID, organization_id: uuid.UUID) -> PurchaseOrder:
        po = await self.get_purchase_order(po_id, organization_id)
        if po.status != PurchaseOrderStatus.DRAFT:
            raise ValidationError(f"Only draft purchase orders can be sent (this one is '{po.status.value}').")
        updated = await self.repo.update(po, status=PurchaseOrderStatus.SENT)
        logger.info("purchase_order_sent", po_id=str(po_id))
        return updated

    async def cancel_purchase_order(self, po_id: uuid.UUID, organization_id: uuid.UUID) -> PurchaseOrder:
        po = await self.get_purchase_order(po_id, organization_id)
        if po.status in (PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.CANCELLED):
            raise ValidationError(f"A purchase order that is '{po.status.value}' cannot be cancelled.")
        if any(float(line.quantity_received) > 0 for line in po.lines):
            raise ValidationError("Cannot cancel a purchase order that already has goods received against it.")
        updated = await self.repo.update(po, status=PurchaseOrderStatus.CANCELLED)
        logger.info("purchase_order_cancelled", po_id=str(po_id))
        return updated


class GoodsReceiptService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = GoodsReceiptRepository(db)
        self.po_repo = PurchaseOrderRepository(db)
        self.warehouse_repo = WarehouseRepository(db)
        self.stock_service = StockService(db)

    async def receive_goods(
        self,
        organization_id: uuid.UUID,
        purchase_order_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        receipt_number: str,
        receipt_date: datetime,
        lines: list[dict],
        notes: str | None = None,
        received_by_user_id: uuid.UUID | None = None,
    ) -> GoodsReceipt:
        po = await self.po_repo.get_by_id(purchase_order_id, organization_id)
        if not po:
            raise NotFoundError("Purchase order", purchase_order_id)
        if po.status not in _RECEIVABLE_STATUSES:
            raise ValidationError(
                f"Goods can only be received against a purchase order that is 'sent' or "
                f"'partially_received' (this one is '{po.status.value}')."
            )

        warehouse = await self.warehouse_repo.get_by_id(warehouse_id, organization_id)
        if not warehouse:
            raise NotFoundError("Warehouse", warehouse_id)

        existing = await self.repo.get_by_number(organization_id, receipt_number)
        if existing:
            raise ConflictError(f"A goods receipt with number '{receipt_number}' already exists.")

        po_lines_by_id = {line.id: line for line in po.lines}
        for line in lines:
            po_line = po_lines_by_id.get(line["purchase_order_line_id"])
            if po_line is None:
                raise NotFoundError("Purchase order line", line["purchase_order_line_id"])
            if line["quantity_received"] > po_line.quantity_remaining + 0.001:
                raise ValidationError(
                    f"Cannot receive {line['quantity_received']} for line '{po_line.description}': "
                    f"only {po_line.quantity_remaining} remaining on the purchase order."
                )

        receipt = await self.repo.create(
            lines=lines,
            organization_id=organization_id,
            purchase_order_id=purchase_order_id,
            warehouse_id=warehouse_id,
            receipt_number=receipt_number,
            receipt_date=receipt_date,
            notes=notes,
            received_by_user_id=received_by_user_id,
        )

        for line in lines:
            po_line = po_lines_by_id[line["purchase_order_line_id"]]
            await self.po_repo.update_line(
                po_line, quantity_received=float(po_line.quantity_received) + line["quantity_received"]
            )
            await self.stock_service.receive_stock(
                organization_id=organization_id,
                item_id=po_line.item_id,
                warehouse_id=warehouse_id,
                quantity=line["quantity_received"],
                unit_cost=line["unit_cost"],
                transaction_date=receipt_date,
                reference_type="goods_receipt",
                reference_id=receipt.id,
                created_by_user_id=received_by_user_id,
            )

        refreshed_po = await self.po_repo.get_by_id(purchase_order_id, organization_id)
        fully_received = all(
            float(line.quantity_received) >= float(line.quantity_ordered) - 0.001 for line in refreshed_po.lines
        )
        new_status = PurchaseOrderStatus.RECEIVED if fully_received else PurchaseOrderStatus.PARTIALLY_RECEIVED
        await self.po_repo.update(refreshed_po, status=new_status)

        logger.info("goods_received", receipt_id=str(receipt.id), purchase_order_id=str(purchase_order_id))
        return receipt

    async def get_receipt(self, receipt_id: uuid.UUID, organization_id: uuid.UUID) -> GoodsReceipt:
        receipt = await self.repo.get_by_id(receipt_id, organization_id)
        if not receipt:
            raise NotFoundError("Goods receipt", receipt_id)
        return receipt

    async def list_for_purchase_order(self, purchase_order_id: uuid.UUID, organization_id: uuid.UUID) -> list[GoodsReceipt]:
        po = await self.po_repo.get_by_id(purchase_order_id, organization_id)
        if not po:
            raise NotFoundError("Purchase order", purchase_order_id)
        return await self.repo.list_for_purchase_order(purchase_order_id)
