"""
Accounting / Ledger — ORM models.

`Account` is the Chart of Accounts: the hierarchy of accounts (Assets,
Liabilities, Equity, Income, Expense) every posting in the module
ultimately lands on. There is deliberately no separate "Ledger" table —
the general ledger is a *view* over `journals.JournalLine` grouped by
account, computed live in `service.py` (same "no redundant table"
approach as Pentrix's Leaderboard and Examinations' Results), so account
balances can never drift out of sync with the journal itself.
"""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401


class AccountType(str, enum.Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


# Accounts of these types increase with a debit; the rest increase with a credit.
DEBIT_NORMAL_TYPES = {AccountType.ASSET, AccountType.EXPENSE}


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Account(TimestampedBase):
    __tablename__ = "accounting_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_account_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, name="account_type", values_callable=_values), nullable=False, index=True
    )
    account_subtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    opening_balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    is_system_account: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def is_debit_normal(self) -> bool:
        return self.account_type in DEBIT_NORMAL_TYPES
