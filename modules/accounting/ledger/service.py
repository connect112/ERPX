import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.ledger.models import Account, AccountType
from modules.accounting.ledger.repository import AccountRepository

logger = get_logger(__name__)


class AccountService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AccountRepository(db)

    async def create_account(
        self, organization_id: uuid.UUID, code: str, parent_account_id: uuid.UUID | None, **fields
    ) -> Account:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"An account with code '{code}' already exists.")
        if parent_account_id is not None:
            parent = await self.repo.get_by_id(parent_account_id, organization_id)
            if not parent:
                raise NotFoundError("Parent account", parent_account_id)
        account = await self.repo.create(
            organization_id=organization_id, code=code, parent_account_id=parent_account_id, **fields
        )
        logger.info("account_created", account_id=str(account.id), code=code)
        return account

    async def get_account(self, account_id: uuid.UUID, organization_id: uuid.UUID) -> Account:
        account = await self.repo.get_by_id(account_id, organization_id)
        if not account:
            raise NotFoundError("Account", account_id)
        return account

    async def get_or_raise_by_code(self, organization_id: uuid.UUID, code: str) -> Account:
        account = await self.repo.get_by_code(organization_id, code)
        if not account:
            raise NotFoundError("Account", code)
        return account

    async def list_accounts(self, organization_id: uuid.UUID, **filters) -> tuple[list[Account], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_account(
        self, account_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Account:
        account = await self.get_account(account_id, organization_id)
        if account.is_system_account and fields.get("is_active") is False:
            raise ValidationError("System accounts cannot be deactivated.")
        updated = await self.repo.update(account, **fields)
        logger.info("account_updated", account_id=str(account_id))
        return updated

    async def get_account_balance(
        self, account_id: uuid.UUID, organization_id: uuid.UUID, as_of_date: date | None = None
    ) -> dict:
        """
        Computed live from posted JournalLines — never a cached/stored
        balance, so it can never drift out of sync with the journal.
        """
        # Imported lazily to avoid a module-level import cycle: journals
        # depends on ledger.Account, ledger's balance view depends on
        # journals.JournalLine.
        from modules.accounting.journals.models import JournalEntry, JournalEntryStatus, JournalLine

        account = await self.get_account(account_id, organization_id)

        conditions = [
            JournalLine.account_id == account_id,
            JournalEntry.id == JournalLine.journal_entry_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        ]
        if as_of_date is not None:
            cutoff = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
            conditions.append(JournalEntry.entry_date <= cutoff)

        result = await self.db.execute(
            select(JournalLine.debit, JournalLine.credit).where(*conditions)
        )
        rows = result.all()
        total_debit = sum(float(r.debit) for r in rows)
        total_credit = sum(float(r.credit) for r in rows)

        if account.is_debit_normal:
            closing_balance = float(account.opening_balance) + total_debit - total_credit
        else:
            closing_balance = float(account.opening_balance) + total_credit - total_debit

        return {
            "account_id": account.id,
            "code": account.code,
            "name": account.name,
            "account_type": account.account_type,
            "as_of_date": as_of_date,
            "opening_balance": float(account.opening_balance),
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": closing_balance,
        }
