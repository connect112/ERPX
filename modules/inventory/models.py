"""
Inventory module — ORM models.

There is deliberately no stored "stock on hand" column anywhere in this
module: `StockTransaction` is an append-only movement ledger (receipts,
issues, adjustments, transfers), and both quantity-on-hand and average
unit cost are computed live in `service.py` by aggregating it — the same
"no redundant balance" principle as the Accounting Ledger's account
balances and Leave's balances. A stock level can never drift out of
sync with its movement history because it IS that history, aggregated.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class StockTransactionType(str, enum.Enum):
    PURCHASE_RECEIPT = "purchase_receipt"
    SALE_ISSUE = "sale_issue"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


# Transaction types that increase quantity on hand; every other type decreases it.
INCREASING_TRANSACTION_TYPES = {
    StockTransactionType.PURCHASE_RECEIPT,
    StockTransactionType.ADJUSTMENT_IN,
    StockTransactionType.TRANSFER_IN,
}


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ItemCategory(TimestampedBase):
    __tablename__ = "inventory_item_categories"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_item_category_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Warehouse(TimestampedBase):
    __tablename__ = "inventory_warehouses"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_warehouse_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InventoryItem(TimestampedBase):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("organization_id", "sku", name="uq_inventory_item_org_sku"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventory_item_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False)
    reorder_level: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    reorder_quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    standard_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StockTransaction(TimestampedBase):
    __tablename__ = "inventory_stock_transactions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    transaction_type: Mapped[StockTransactionType] = mapped_column(
        SAEnum(StockTransactionType, name="stock_transaction_type", values_callable=_values), nullable=False, index=True
    )
    # Always a positive magnitude; direction (increase/decrease) is derived
    # from `transaction_type` via `INCREASING_TRANSACTION_TYPES`.
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
