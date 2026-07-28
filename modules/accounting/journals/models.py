"""
Accounting / Journals — ORM models.

`JournalEntry` + `JournalLine` are the single source of truth for every
financial movement in the platform: Invoices, Receipts, Expenses, and
Payments never post directly to an `Account` balance — they all call
`JournalService.post_transaction(...)`, which is the only place a
balanced (debits == credits) double-entry posting is created. This keeps
the debit/credit invariant enforced in exactly one place instead of
duplicated across four modules.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
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
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class JournalEntryStatus(str, enum.Enum):
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


class JournalSourceModule(str, enum.Enum):
    MANUAL = "manual"
    INVOICES = "invoices"
    RECEIPTS = "receipts"
    EXPENSES = "expenses"
    PAYMENTS = "payments"
    BANK = "bank"
    PAYROLL = "payroll"
    ASSETS = "assets"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class JournalEntry(TimestampedBase):
    __tablename__ = "accounting_journal_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "entry_number", name="uq_journal_entry_org_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    entry_number: Mapped[str] = mapped_column(String(50), nullable=False)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_module: Mapped[JournalSourceModule] = mapped_column(
        SAEnum(JournalSourceModule, name="journal_source_module", values_callable=_values),
        default=JournalSourceModule.MANUAL,
        server_default=JournalSourceModule.MANUAL.value,
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    status: Mapped[JournalEntryStatus] = mapped_column(
        SAEnum(JournalEntryStatus, name="journal_entry_status", values_callable=_values),
        default=JournalEntryStatus.DRAFT,
        server_default=JournalEntryStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    reversed_by_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_order",
    )


class JournalLine(TimestampedBase):
    __tablename__ = "accounting_journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_line_non_negative"),
        CheckConstraint(
            "NOT (debit > 0 AND credit > 0)", name="ck_journal_line_single_sided"
        ),
    )

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    debit: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    credit: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    line_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    journal_entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
