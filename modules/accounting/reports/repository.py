"""
Accounting / Reports — read-only aggregation queries.

Every report in this module (`ReportService`) is computed live from
`Account` + posted `JournalLine` rows — there is no stored report table
anywhere in this module, the same principle used throughout Accounting
(Ledger balances, GST returns): a report can never drift out of sync
with the journal because it IS the journal, aggregated differently.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.journals.models import JournalEntry, JournalEntryStatus, JournalLine
from modules.accounting.ledger.models import Account, AccountType


class ReportsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def account_activity(
        self,
        organization_id: uuid.UUID,
        account_types: list[AccountType] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """Per-account (code, name, type, opening_balance, total_debit, total_credit) within an optional date window."""
        from sqlalchemy import func

        conditions = [
            Account.organization_id == organization_id,
            JournalEntry.id == JournalLine.journal_entry_id,
            JournalLine.account_id == Account.id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        ]
        if account_types:
            conditions.append(Account.account_type.in_(account_types))
        if date_from is not None:
            conditions.append(JournalEntry.entry_date >= date_from)
        if date_to is not None:
            conditions.append(JournalEntry.entry_date <= date_to)

        result = await self.db.execute(
            select(
                Account.id,
                Account.code,
                Account.name,
                Account.account_type,
                Account.opening_balance,
                func.coalesce(func.sum(JournalLine.debit), 0).label("total_debit"),
                func.coalesce(func.sum(JournalLine.credit), 0).label("total_credit"),
            )
            .where(*conditions)
            .group_by(Account.id, Account.code, Account.name, Account.account_type, Account.opening_balance)
            .order_by(Account.code.asc())
        )
        return [
            {
                "account_id": row.id,
                "code": row.code,
                "name": row.name,
                "account_type": row.account_type,
                "opening_balance": float(row.opening_balance),
                "total_debit": float(row.total_debit),
                "total_credit": float(row.total_credit),
            }
            for row in result.all()
        ]

    async def all_accounts(self, organization_id: uuid.UUID, account_types: list[AccountType] | None = None):
        conditions = [Account.organization_id == organization_id, Account.is_active.is_(True)]
        if account_types:
            conditions.append(Account.account_type.in_(account_types))
        result = await self.db.execute(select(Account).where(*conditions).order_by(Account.code.asc()))
        return list(result.scalars().all())
