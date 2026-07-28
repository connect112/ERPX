"""
Accounting / Invoices — ORM models.

`Invoice` is the accounts-receivable sales document. Posting one
(`InvoiceService.post_invoice`) is the only place Invoices touch the
General Ledger: it calls `JournalService.post_transaction` with lines
built from the invoice's receivable/revenue/tax/discount accounts, so
the invoice never writes to `JournalEntry`/`JournalLine` directly.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.accounting.customers.models import Customer  # noqa: F401
from modules.accounting.gst.models import GSTRate  # noqa: F401
from modules.accounting.journals.models import JournalEntry  # noqa: F401
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Invoice(TimestampedBase):
    __tablename__ = "accounting_invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number", name="uq_invoice_org_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    receivable_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    tax_payable_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    discount_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )

    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_interstate: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)

    subtotal_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)

    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status", values_callable=_values),
        default=InvoiceStatus.DRAFT,
        server_default=InvoiceStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.line_order"
    )

    @property
    def outstanding_amount(self) -> float:
        return float(self.total_amount) - float(self.amount_paid)


class InvoiceLine(TimestampedBase):
    __tablename__ = "accounting_invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revenue_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    gst_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    line_subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    line_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")
