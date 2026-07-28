"""
Accounting / Receipts — ORM models.

A `Receipt` records money received from a `Customer`, either against a
specific `Invoice` or as an on-account/advance receipt (`invoice_id`
null). Posting one debits the bank/cash account and credits Accounts
Receivable via `JournalService`, then calls back into
`InvoiceService.apply_payment` to update the invoice's paid amount and
status — the same cross-module call pattern Payments uses against
Expenses.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.accounting.bank.models import BankAccount  # noqa: F401
from modules.accounting.customers.models import Customer  # noqa: F401
from modules.accounting.invoices.models import Invoice  # noqa: F401
from modules.accounting.journals.models import JournalEntry  # noqa: F401
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class PaymentMode(str, enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    UPI = "upi"
    CARD = "card"
    ONLINE = "online"


class ReceiptStatus(str, enum.Enum):
    CLEARED = "cleared"
    VOIDED = "voided"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Receipt(TimestampedBase):
    __tablename__ = "accounting_receipts"
    __table_args__ = (
        UniqueConstraint("organization_id", "receipt_number", name="uq_receipt_org_number"),
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
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_invoices.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Populated directly for cash receipts, or derived from `bank_account_id`
    # (its linked GL account) for bank-routed receipts — see `ReceiptService.create_receipt`.
    deposit_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )

    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False)
    receipt_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    payment_mode: Mapped[PaymentMode] = mapped_column(
        SAEnum(PaymentMode, name="ar_payment_mode", values_callable=_values), nullable=False
    )
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ReceiptStatus] = mapped_column(
        SAEnum(ReceiptStatus, name="receipt_status", values_callable=_values),
        default=ReceiptStatus.CLEARED,
        server_default=ReceiptStatus.CLEARED.value,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
