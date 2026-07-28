"""create accounting tables (ledger, journals, customers, vendors, gst, tds, invoices, receipts, expenses, payments, bank, reports)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

account_type_enum = postgresql.ENUM("asset", "liability", "equity", "income", "expense", name="account_type")
journal_entry_status_enum = postgresql.ENUM("draft", "posted", "reversed", name="journal_entry_status")
journal_source_module_enum = postgresql.ENUM(
    "manual", "invoices", "receipts", "expenses", "payments", "bank", name="journal_source_module"
)
customer_type_enum = postgresql.ENUM("individual", "student", "corporate", name="customer_type")
invoice_status_enum = postgresql.ENUM(
    "draft", "sent", "partially_paid", "paid", "overdue", "cancelled", name="invoice_status"
)
ar_payment_mode_enum = postgresql.ENUM(
    "cash", "bank_transfer", "cheque", "upi", "card", "online", name="ar_payment_mode"
)
receipt_status_enum = postgresql.ENUM("cleared", "voided", name="receipt_status")
expense_status_enum = postgresql.ENUM(
    "draft", "approved", "partially_paid", "paid", "rejected", "cancelled", name="expense_status"
)
ap_payment_mode_enum = postgresql.ENUM(
    "cash", "bank_transfer", "cheque", "upi", "online", name="ap_payment_mode"
)
payment_status_enum = postgresql.ENUM("cleared", "voided", name="payment_status")
bank_account_type_enum = postgresql.ENUM("savings", "current", "cash", name="bank_account_type")
bank_transaction_source_enum = postgresql.ENUM(
    "manual", "receipt", "payment", "import", name="bank_transaction_source"
)

_ALL_ENUMS = [
    account_type_enum,
    journal_entry_status_enum,
    journal_source_module_enum,
    customer_type_enum,
    invoice_status_enum,
    ar_payment_mode_enum,
    receipt_status_enum,
    expense_status_enum,
    ap_payment_mode_enum,
    payment_status_enum,
    bank_account_type_enum,
    bank_transaction_source_enum,
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
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- Ledger: Accounts ----
    op.create_table(
        "accounting_accounts",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("account_type", postgresql.ENUM("asset", "liability", "equity", "income", "expense", name="account_type", create_type=False), nullable=False),
        sa.Column("account_subtype", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_system_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_account_org_code"),
    )
    op.create_index("ix_accounting_accounts_organization_id", "accounting_accounts", ["organization_id"])
    op.create_index("ix_accounting_accounts_parent_account_id", "accounting_accounts", ["parent_account_id"])
    op.create_index("ix_accounting_accounts_account_type", "accounting_accounts", ["account_type"])

    # ---- GST Rates ----
    op.create_table(
        "accounting_gst_rates",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("rate_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("hsn_sac_code", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "name", name="uq_gst_rate_org_name"),
    )
    op.create_index("ix_accounting_gst_rates_organization_id", "accounting_gst_rates", ["organization_id"])

    # ---- Customers ----
    op.create_table(
        "accounting_customers",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("customer_type", postgresql.ENUM("individual", "student", "corporate", name="customer_type", create_type=False), nullable=False, server_default="individual"),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("billing_address_line1", sa.String(length=255), nullable=True),
        sa.Column("billing_address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "customer_code", name="uq_customer_org_code"),
    )
    op.create_index("ix_accounting_customers_organization_id", "accounting_customers", ["organization_id"])
    op.create_index("ix_accounting_customers_student_id", "accounting_customers", ["student_id"])

    # ---- Vendors ----
    op.create_table(
        "accounting_vendors",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("pan_number", sa.String(length=10), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("bank_account_number", sa.String(length=34), nullable=True),
        sa.Column("bank_ifsc_code", sa.String(length=11), nullable=True),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "vendor_code", name="uq_vendor_org_code"),
    )
    op.create_index("ix_accounting_vendors_organization_id", "accounting_vendors", ["organization_id"])

    # ---- Journal Entries & Lines ----
    op.create_table(
        "accounting_journal_entries",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_number", sa.String(length=50), nullable=False),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("source_module", postgresql.ENUM("manual", "invoices", "receipts", "expenses", "payments", "bank", name="journal_source_module", create_type=False), nullable=False, server_default="manual"),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", postgresql.ENUM("draft", "posted", "reversed", name="journal_entry_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("reversed_by_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("organization_id", "entry_number", name="uq_journal_entry_org_number"),
    )
    op.create_index("ix_accounting_journal_entries_organization_id", "accounting_journal_entries", ["organization_id"])
    op.create_index("ix_accounting_journal_entries_entry_date", "accounting_journal_entries", ["entry_date"])
    op.create_index("ix_accounting_journal_entries_source_module", "accounting_journal_entries", ["source_module"])
    op.create_index("ix_accounting_journal_entries_source_id", "accounting_journal_entries", ["source_id"])
    op.create_index("ix_accounting_journal_entries_status", "accounting_journal_entries", ["status"])

    op.create_table(
        "accounting_journal_lines",
        *_tc(),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_line_non_negative"),
        sa.CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_journal_line_single_sided"),
    )
    op.create_index("ix_accounting_journal_lines_journal_entry_id", "accounting_journal_lines", ["journal_entry_id"])
    op.create_index("ix_accounting_journal_lines_account_id", "accounting_journal_lines", ["account_id"])

    # ---- TDS Sections & Deductions ----
    op.create_table(
        "accounting_tds_sections",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_code", sa.String(length=10), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("rate_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("threshold_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "section_code", name="uq_tds_section_org_code"),
    )
    op.create_index("ix_accounting_tds_sections_organization_id", "accounting_tds_sections", ["organization_id"])

    op.create_table(
        "accounting_tds_deductions",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tds_section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_tds_sections.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tds_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("financial_year", sa.String(length=9), nullable=False),
        sa.Column("certificate_number", sa.String(length=50), nullable=True),
        sa.Column("deduction_date", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_accounting_tds_deductions_organization_id", "accounting_tds_deductions", ["organization_id"])
    op.create_index("ix_accounting_tds_deductions_vendor_id", "accounting_tds_deductions", ["vendor_id"])
    op.create_index("ix_accounting_tds_deductions_tds_section_id", "accounting_tds_deductions", ["tds_section_id"])
    op.create_index("ix_accounting_tds_deductions_payment_id", "accounting_tds_deductions", ["payment_id"])
    op.create_index("ix_accounting_tds_deductions_financial_year", "accounting_tds_deductions", ["financial_year"])

    # ---- Bank Accounts & Transactions ----
    op.create_table(
        "accounting_bank_accounts",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("account_type", postgresql.ENUM("savings", "current", "cash", name="bank_account_type", create_type=False), nullable=False, server_default="current"),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("account_number", sa.String(length=34), nullable=True),
        sa.Column("ifsc_code", sa.String(length=11), nullable=True),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_accounting_bank_accounts_organization_id", "accounting_bank_accounts", ["organization_id"])

    op.create_table(
        "accounting_bank_transactions",
        *_tc(),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_bank_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("debit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("source", postgresql.ENUM("manual", "receipt", "payment", "import", name="bank_transaction_source", create_type=False), nullable=False, server_default="manual"),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_reconciled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_accounting_bank_transactions_bank_account_id", "accounting_bank_transactions", ["bank_account_id"])
    op.create_index("ix_accounting_bank_transactions_transaction_date", "accounting_bank_transactions", ["transaction_date"])
    op.create_index("ix_accounting_bank_transactions_source_id", "accounting_bank_transactions", ["source_id"])
    op.create_index("ix_accounting_bank_transactions_is_reconciled", "accounting_bank_transactions", ["is_reconciled"])

    # ---- Invoices & Invoice Lines ----
    op.create_table(
        "accounting_invoices",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receivable_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tax_payable_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("discount_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_number", sa.String(length=50), nullable=False),
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_interstate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("subtotal_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", postgresql.ENUM("draft", "sent", "partially_paid", "paid", "overdue", "cancelled", name="invoice_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_org_number"),
    )
    op.create_index("ix_accounting_invoices_organization_id", "accounting_invoices", ["organization_id"])
    op.create_index("ix_accounting_invoices_customer_id", "accounting_invoices", ["customer_id"])
    op.create_index("ix_accounting_invoices_invoice_date", "accounting_invoices", ["invoice_date"])
    op.create_index("ix_accounting_invoices_due_date", "accounting_invoices", ["due_date"])
    op.create_index("ix_accounting_invoices_status", "accounting_invoices", ["status"])

    op.create_table(
        "accounting_invoice_lines",
        *_tc(),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revenue_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("gst_rate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_accounting_invoice_lines_invoice_id", "accounting_invoice_lines", ["invoice_id"])

    # ---- Receipts ----
    op.create_table(
        "accounting_receipts",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_invoices.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("deposit_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_bank_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("receipt_number", sa.String(length=50), nullable=False),
        sa.Column("receipt_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_mode", postgresql.ENUM("cash", "bank_transfer", "cheque", "upi", "card", "online", name="ar_payment_mode", create_type=False), nullable=False),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("status", postgresql.ENUM("cleared", "voided", name="receipt_status", create_type=False), nullable=False, server_default="cleared"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "receipt_number", name="uq_receipt_org_number"),
    )
    op.create_index("ix_accounting_receipts_organization_id", "accounting_receipts", ["organization_id"])
    op.create_index("ix_accounting_receipts_customer_id", "accounting_receipts", ["customer_id"])
    op.create_index("ix_accounting_receipts_invoice_id", "accounting_receipts", ["invoice_id"])
    op.create_index("ix_accounting_receipts_receipt_date", "accounting_receipts", ["receipt_date"])
    op.create_index("ix_accounting_receipts_status", "accounting_receipts", ["status"])

    # ---- Expenses ----
    op.create_table(
        "accounting_expenses",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expense_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payable_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("input_tax_credit_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("gst_rate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expense_number", sa.String(length=50), nullable=False),
        sa.Column("expense_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_interstate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("subtotal_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", postgresql.ENUM("draft", "approved", "partially_paid", "paid", "rejected", "cancelled", name="expense_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("attachment_url", sa.String(length=512), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "expense_number", name="uq_expense_org_number"),
    )
    op.create_index("ix_accounting_expenses_organization_id", "accounting_expenses", ["organization_id"])
    op.create_index("ix_accounting_expenses_vendor_id", "accounting_expenses", ["vendor_id"])
    op.create_index("ix_accounting_expenses_expense_date", "accounting_expenses", ["expense_date"])
    op.create_index("ix_accounting_expenses_category", "accounting_expenses", ["category"])
    op.create_index("ix_accounting_expenses_status", "accounting_expenses", ["status"])

    # ---- Payments ----
    op.create_table(
        "accounting_payments",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expense_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_expenses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_bank_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tds_payable_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("tds_section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_tds_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tds_deduction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_tds_deductions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payment_number", sa.String(length=50), nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tds_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_mode", postgresql.ENUM("cash", "bank_transfer", "cheque", "upi", "online", name="ap_payment_mode", create_type=False), nullable=False),
        sa.Column("reference_number", sa.String(length=100), nullable=True),
        sa.Column("status", postgresql.ENUM("cleared", "voided", name="payment_status", create_type=False), nullable=False, server_default="cleared"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "payment_number", name="uq_payment_org_number"),
    )
    op.create_index("ix_accounting_payments_organization_id", "accounting_payments", ["organization_id"])
    op.create_index("ix_accounting_payments_vendor_id", "accounting_payments", ["vendor_id"])
    op.create_index("ix_accounting_payments_expense_id", "accounting_payments", ["expense_id"])
    op.create_index("ix_accounting_payments_payment_date", "accounting_payments", ["payment_date"])
    op.create_index("ix_accounting_payments_status", "accounting_payments", ["status"])


def downgrade() -> None:
    op.drop_table("accounting_payments")
    op.drop_table("accounting_expenses")
    op.drop_table("accounting_receipts")
    op.drop_table("accounting_invoice_lines")
    op.drop_table("accounting_invoices")
    op.drop_table("accounting_bank_transactions")
    op.drop_table("accounting_bank_accounts")
    op.drop_table("accounting_tds_deductions")
    op.drop_table("accounting_tds_sections")
    op.drop_table("accounting_journal_lines")
    op.drop_table("accounting_journal_entries")
    op.drop_table("accounting_vendors")
    op.drop_table("accounting_customers")
    op.drop_table("accounting_gst_rates")
    op.drop_table("accounting_accounts")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
