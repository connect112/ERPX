"""
Accounting / Bank — ORM models.

`BankAccount` mirrors a real bank/cash account and is mapped 1:1 to an
Asset `Account` in the Chart of Accounts (`gl_account_id`) so its ledger
balance and its bank-statement balance are always the same underlying
number viewed two ways. `BankTransaction` is the statement line used for
reconciliation — it does not itself carry a journal posting when it
mirrors a Receipt/Payment (those already post through `JournalService`);
it only posts its own entry for genuinely bank-only movements (charges,
interest) via `BankService.record_transaction`.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class BankAccountType(str, enum.Enum):
    SAVINGS = "savings"
    CURRENT = "current"
    CASH = "cash"


class BankTransactionSource(str, enum.Enum):
    MANUAL = "manual"
    RECEIPT = "receipt"
    PAYMENT = "payment"
    IMPORT = "import"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class BankAccount(TimestampedBase):
    __tablename__ = "accounting_bank_accounts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    gl_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), unique=True, nullable=False
    )

    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[BankAccountType] = mapped_column(
        SAEnum(BankAccountType, name="bank_account_type", values_callable=_values),
        default=BankAccountType.CURRENT,
        server_default=BankAccountType.CURRENT.value,
        nullable=False,
    )
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    ifsc_code: Mapped[str | None] = mapped_column(String(11), nullable=True)
    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BankTransaction(TimestampedBase):
    __tablename__ = "accounting_bank_transactions"

    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )

    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    debit_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    credit_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    source: Mapped[BankTransactionSource] = mapped_column(
        SAEnum(BankTransactionSource, name="bank_transaction_source", values_callable=_values),
        default=BankTransactionSource.MANUAL,
        server_default=BankTransactionSource.MANUAL.value,
        nullable=False,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
