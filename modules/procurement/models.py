"""
Procurement module — ORM models.

`PurchaseOrder` doubles as the requisition/approval object (its DRAFT
status is the pending-approval stage) rather than a separate
requisition entity — one procurement primitive with a status workflow,
not two overlapping ones. Receiving goods against a PO
(`GoodsReceiptService.receive_goods`) is the integration point with
Inventory: each `GoodsReceiptLine` calls `StockService.receive_stock`
to actually increase stock on hand. Converting a received PO into a
payable AP `Expense` is a deliberate manual step for the finance team
(via Accounting), not automatic — the same boundary CRM draws around
`Admission` -> `Student` creation.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.accounting.gst.models import GSTRate  # noqa: F401
from modules.accounting.vendors.models import Vendor  # noqa: F401
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.inventory.models import InventoryItem, Warehouse  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class PurchaseOrder(TimestampedBase):
    __tablename__ = "procurement_purchase_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "po_number", name="uq_purchase_order_org_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_vendors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    po_number: Mapped[str] = mapped_column(String(50), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expected_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        SAEnum(PurchaseOrderStatus, name="purchase_order_status", values_callable=_values),
        default=PurchaseOrderStatus.DRAFT,
        server_default=PurchaseOrderStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    subtotal_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderLine(TimestampedBase):
    __tablename__ = "procurement_purchase_order_lines"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False
    )
    gst_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity_ordered: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    quantity_received: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    line_subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")

    @property
    def quantity_remaining(self) -> float:
        return float(self.quantity_ordered) - float(self.quantity_received)


class GoodsReceipt(TimestampedBase):
    __tablename__ = "procurement_goods_receipts"
    __table_args__ = (
        UniqueConstraint("organization_id", "receipt_number", name="uq_goods_receipt_org_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procurement_purchase_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False)
    receipt_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["GoodsReceiptLine"]] = relationship(
        back_populates="goods_receipt", cascade="all, delete-orphan"
    )


class GoodsReceiptLine(TimestampedBase):
    __tablename__ = "procurement_goods_receipt_lines"

    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procurement_goods_receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purchase_order_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("procurement_purchase_order_lines.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_received: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    goods_receipt: Mapped["GoodsReceipt"] = relationship(back_populates="lines")
