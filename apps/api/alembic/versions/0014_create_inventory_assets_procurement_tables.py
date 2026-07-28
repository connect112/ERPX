"""create inventory, assets, and procurement tables

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

stock_transaction_type_enum = postgresql.ENUM(
    "purchase_receipt", "sale_issue", "adjustment_in", "adjustment_out", "transfer_in", "transfer_out",
    name="stock_transaction_type",
)
depreciation_method_enum = postgresql.ENUM("straight_line", "declining_balance", name="depreciation_method")
asset_status_enum = postgresql.ENUM("in_use", "in_storage", "under_maintenance", "disposed", name="asset_status")
depreciation_run_status_enum = postgresql.ENUM("draft", "posted", "cancelled", name="depreciation_run_status")
purchase_order_status_enum = postgresql.ENUM(
    "draft", "sent", "partially_received", "received", "cancelled", name="purchase_order_status"
)

_ALL_ENUMS = [
    stock_transaction_type_enum,
    depreciation_method_enum,
    asset_status_enum,
    depreciation_run_status_enum,
    purchase_order_status_enum,
]


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # `journal_source_module` (created in 0011) gains a value for asset-sourced
    # postings (depreciation, disposal), alongside 'payroll' added in 0013.
    op.execute("ALTER TYPE journal_source_module ADD VALUE IF NOT EXISTS 'assets'")

    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    # ==================== Inventory ====================

    op.create_table(
        "inventory_item_categories",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_item_category_org_code"),
    )
    op.create_index("ix_inventory_item_categories_organization_id", "inventory_item_categories", ["organization_id"])

    op.create_table(
        "inventory_warehouses",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_warehouse_org_code"),
    )
    op.create_index("ix_inventory_warehouses_organization_id", "inventory_warehouses", ["organization_id"])

    op.create_table(
        "inventory_items",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_item_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sku", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_of_measure", sa.String(length=20), nullable=False),
        sa.Column("reorder_level", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("reorder_quantity", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("standard_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "sku", name="uq_inventory_item_org_sku"),
    )
    op.create_index("ix_inventory_items_organization_id", "inventory_items", ["organization_id"])
    op.create_index("ix_inventory_items_category_id", "inventory_items", ["category_id"])

    op.create_table(
        "inventory_stock_transactions",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("transaction_type", postgresql.ENUM("purchase_receipt", "sale_issue", "adjustment_in", "adjustment_out", "transfer_in", "transfer_out", name="stock_transaction_type", create_type=False), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_inventory_stock_transactions_organization_id", "inventory_stock_transactions", ["organization_id"])
    op.create_index("ix_inventory_stock_transactions_warehouse_id", "inventory_stock_transactions", ["warehouse_id"])
    op.create_index("ix_inventory_stock_transactions_item_id", "inventory_stock_transactions", ["item_id"])
    op.create_index("ix_inventory_stock_transactions_transaction_type", "inventory_stock_transactions", ["transaction_type"])
    op.create_index("ix_inventory_stock_transactions_transaction_date", "inventory_stock_transactions", ["transaction_date"])
    op.create_index("ix_inventory_stock_transactions_reference_id", "inventory_stock_transactions", ["reference_id"])

    # ==================== Assets ====================

    op.create_table(
        "asset_categories",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("default_useful_life_years", sa.Integer(), nullable=False),
        sa.Column("default_depreciation_method", postgresql.ENUM("straight_line", "declining_balance", name="depreciation_method", create_type=False), nullable=False, server_default="straight_line"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_asset_category_org_code"),
    )
    op.create_index("ix_asset_categories_organization_id", "asset_categories", ["organization_id"])

    op.create_table(
        "assets",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to_employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("accumulated_depreciation_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("depreciation_expense_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("disposal_journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("purchase_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("salvage_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("useful_life_years", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", postgresql.ENUM("straight_line", "declining_balance", name="depreciation_method", create_type=False), nullable=False, server_default="straight_line"),
        sa.Column("status", postgresql.ENUM("in_use", "in_storage", "under_maintenance", "disposed", name="asset_status", create_type=False), nullable=False, server_default="in_use"),
        sa.Column("disposal_date", sa.Date(), nullable=True),
        sa.Column("disposal_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "asset_code", name="uq_asset_org_code"),
    )
    op.create_index("ix_assets_organization_id", "assets", ["organization_id"])
    op.create_index("ix_assets_category_id", "assets", ["category_id"])
    op.create_index("ix_assets_assigned_to_employee_id", "assets", ["assigned_to_employee_id"])
    op.create_index("ix_assets_status", "assets", ["status"])

    op.create_table(
        "asset_depreciation_runs",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "posted", "cancelled", name="depreciation_run_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("total_depreciation_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "period_year", "period_month", name="uq_depreciation_run_period"),
    )
    op.create_index("ix_asset_depreciation_runs_organization_id", "asset_depreciation_runs", ["organization_id"])
    op.create_index("ix_asset_depreciation_runs_status", "asset_depreciation_runs", ["status"])

    op.create_table(
        "asset_depreciation_entries",
        *_tc(),
        sa.Column("depreciation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_depreciation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depreciation_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("accumulated_depreciation", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_book_value", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("asset_id", "depreciation_run_id", name="uq_depreciation_entry_asset_run"),
    )
    op.create_index("ix_asset_depreciation_entries_depreciation_run_id", "asset_depreciation_entries", ["depreciation_run_id"])
    op.create_index("ix_asset_depreciation_entries_asset_id", "asset_depreciation_entries", ["asset_id"])

    # ==================== Procurement ====================

    op.create_table(
        "procurement_purchase_orders",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("po_number", sa.String(length=50), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_delivery_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", postgresql.ENUM("draft", "sent", "partially_received", "received", "cancelled", name="purchase_order_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("subtotal_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "po_number", name="uq_purchase_order_org_number"),
    )
    op.create_index("ix_procurement_purchase_orders_organization_id", "procurement_purchase_orders", ["organization_id"])
    op.create_index("ix_procurement_purchase_orders_vendor_id", "procurement_purchase_orders", ["vendor_id"])
    op.create_index("ix_procurement_purchase_orders_order_date", "procurement_purchase_orders", ["order_date"])
    op.create_index("ix_procurement_purchase_orders_status", "procurement_purchase_orders", ["status"])

    op.create_table(
        "procurement_purchase_order_lines",
        *_tc(),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("gst_rate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity_received", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_procurement_purchase_order_lines_purchase_order_id", "procurement_purchase_order_lines", ["purchase_order_id"])

    op.create_table(
        "procurement_goods_receipts",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("procurement_purchase_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("received_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("receipt_number", sa.String(length=50), nullable=False),
        sa.Column("receipt_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "receipt_number", name="uq_goods_receipt_org_number"),
    )
    op.create_index("ix_procurement_goods_receipts_organization_id", "procurement_goods_receipts", ["organization_id"])
    op.create_index("ix_procurement_goods_receipts_purchase_order_id", "procurement_goods_receipts", ["purchase_order_id"])
    op.create_index("ix_procurement_goods_receipts_receipt_date", "procurement_goods_receipts", ["receipt_date"])

    op.create_table(
        "procurement_goods_receipt_lines",
        *_tc(),
        sa.Column("goods_receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("procurement_goods_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchase_order_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("procurement_purchase_order_lines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity_received", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_procurement_goods_receipt_lines_goods_receipt_id", "procurement_goods_receipt_lines", ["goods_receipt_id"])


def downgrade() -> None:
    op.drop_table("procurement_goods_receipt_lines")
    op.drop_table("procurement_goods_receipts")
    op.drop_table("procurement_purchase_order_lines")
    op.drop_table("procurement_purchase_orders")
    op.drop_table("asset_depreciation_entries")
    op.drop_table("asset_depreciation_runs")
    op.drop_table("assets")
    op.drop_table("asset_categories")
    op.drop_table("inventory_stock_transactions")
    op.drop_table("inventory_items")
    op.drop_table("inventory_warehouses")
    op.drop_table("inventory_item_categories")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
    # Postgres does not support removing a value from an enum type; the
    # 'assets' value added to journal_source_module is left in place.
