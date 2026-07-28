"""
Accounting / Expenses — ORM models.

An `Expense` is a vendor bill going through a maker-checker workflow
(DRAFT -> APPROVED/REJECTED) before it touches the General Ledger:
approving one is the only place it posts (Dr Expense [+ Dr GST Input
Credit], Cr Accounts Payable) via `JournalService`. `Payments` settles
it afterwards the same way `Receipts` settles an `Invoice`.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.accounting.gst.models import GSTRate  # noqa: F401
from modules.accounting.journals.models import JournalEntry  # noqa: F401
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.accounting.vendors.models import Vendor  # noqa: F401
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class ExpenseStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Expense(TimestampedBase):
    __tablename__ = "accounting_expenses"
    __table_args__ = (
        UniqueConstraint("organization_id", "expense_number", name="uq_expense_org_number"),
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
    expense_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    payable_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    input_tax_credit_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    gst_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    expense_number: Mapped[str] = mapped_column(String(50), nullable=False)
    expense_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_interstate: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)

    subtotal_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)

    status: Mapped[ExpenseStatus] = mapped_column(
        SAEnum(ExpenseStatus, name="expense_status", values_callable=_values),
        default=ExpenseStatus.DRAFT,
        server_default=ExpenseStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    attachment_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def outstanding_amount(self) -> float:
        return float(self.total_amount) - float(self.amount_paid)
