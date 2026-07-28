"""
Accounting / Payments — ORM models.

A `Payment` settles an approved `Expense`: it debits Accounts Payable for
the gross amount, optionally withholds TDS (credited to a TDS Payable
account via `TDSService.compute_and_record_deduction`), and credits the
bank/cash account for the net amount actually paid out.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.accounting.bank.models import BankAccount  # noqa: F401
from modules.accounting.expenses.models import Expense  # noqa: F401
from modules.accounting.journals.models import JournalEntry  # noqa: F401
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.accounting.tds.models import TDSDeduction  # noqa: F401
from modules.accounting.vendors.models import Vendor  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class ApPaymentMode(str, enum.Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    UPI = "upi"
    ONLINE = "online"


class PaymentStatus(str, enum.Enum):
    CLEARED = "cleared"
    VOIDED = "voided"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Payment(TimestampedBase):
    __tablename__ = "accounting_payments"
    __table_args__ = (
        UniqueConstraint("organization_id", "payment_number", name="uq_payment_org_number"),
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
    expense_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_expenses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    tds_payable_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    tds_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_tds_sections.id", ondelete="SET NULL"), nullable=True
    )
    tds_deduction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_tds_deductions.id", ondelete="SET NULL"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )

    payment_number: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tds_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    payment_mode: Mapped[ApPaymentMode] = mapped_column(
        SAEnum(ApPaymentMode, name="ap_payment_mode", values_callable=_values), nullable=False
    )
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status", values_callable=_values),
        default=PaymentStatus.CLEARED,
        server_default=PaymentStatus.CLEARED.value,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
