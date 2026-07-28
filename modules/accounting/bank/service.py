import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.bank.models import BankAccount, BankTransaction, BankTransactionSource
from modules.accounting.bank.repository import BankAccountRepository, BankTransactionRepository
from modules.accounting.journals.models import JournalSourceModule
from modules.accounting.journals.service import JournalService
from modules.accounting.ledger.models import AccountType
from modules.accounting.ledger.repository import AccountRepository

logger = get_logger(__name__)


class BankService:
    """
    `debit_amount`/`credit_amount` on a BankTransaction mirror the GL
    convention for the bank's own Asset account: debit increases the
    balance (money in), credit decreases it (money out) — the same
    direction `AccountService.get_account_balance` uses.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.account_repo = BankAccountRepository(db)
        self.txn_repo = BankTransactionRepository(db)
        self.gl_account_repo = AccountRepository(db)
        self.journal_service = JournalService(db)

    # ---- Bank Accounts ----

    async def create_bank_account(
        self, organization_id: uuid.UUID, gl_account_id: uuid.UUID, **fields
    ) -> BankAccount:
        gl_account = await self.gl_account_repo.get_by_id(gl_account_id, organization_id)
        if not gl_account:
            raise NotFoundError("GL account", gl_account_id)
        if gl_account.account_type != AccountType.ASSET:
            raise ValidationError("A bank account must be linked to an Asset-type GL account.")

        account = await self.account_repo.create(
            organization_id=organization_id, gl_account_id=gl_account_id, **fields
        )
        logger.info("bank_account_created", bank_account_id=str(account.id))
        return account

    async def get_bank_account(self, bank_account_id: uuid.UUID, organization_id: uuid.UUID) -> BankAccount:
        account = await self.account_repo.get_by_id(bank_account_id, organization_id)
        if not account:
            raise NotFoundError("Bank account", bank_account_id)
        return account

    async def list_bank_accounts(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[BankAccount]:
        return await self.account_repo.list_for_organization(organization_id, is_active)

    async def update_bank_account(
        self, bank_account_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> BankAccount:
        account = await self.get_bank_account(bank_account_id, organization_id)
        updated = await self.account_repo.update(account, **fields)
        logger.info("bank_account_updated", bank_account_id=str(bank_account_id))
        return updated

    async def get_balance(
        self, bank_account_id: uuid.UUID, organization_id: uuid.UUID, as_of_date: date | None = None
    ) -> dict:
        account = await self.get_bank_account(bank_account_id, organization_id)
        cutoff = None
        if as_of_date is not None:
            cutoff = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        total_debit, total_credit = await self.txn_repo.sum_for_account(bank_account_id, cutoff)
        closing_balance = float(account.opening_balance) + total_debit - total_credit
        return {
            "bank_account_id": account.id,
            "account_name": account.account_name,
            "as_of_date": as_of_date,
            "opening_balance": float(account.opening_balance),
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": closing_balance,
        }

    # ---- Transactions ----

    async def record_manual_transaction(
        self,
        bank_account_id: uuid.UUID,
        organization_id: uuid.UUID,
        transaction_date: datetime,
        description: str,
        debit_amount: float,
        credit_amount: float,
        contra_account_id: uuid.UUID,
        reference_number: str | None = None,
        created_by_user_id: uuid.UUID | None = None,
    ) -> BankTransaction:
        if debit_amount > 0 and credit_amount > 0:
            raise ValidationError("A bank transaction cannot have both a debit and a credit amount.")
        if debit_amount == 0 and credit_amount == 0:
            raise ValidationError("A bank transaction must have either a debit or a credit amount.")

        bank_account = await self.get_bank_account(bank_account_id, organization_id)
        amount = debit_amount or credit_amount

        lines = (
            [
                {"account_id": bank_account.gl_account_id, "debit": amount, "credit": 0},
                {"account_id": contra_account_id, "debit": 0, "credit": amount},
            ]
            if debit_amount > 0
            else [
                {"account_id": contra_account_id, "debit": amount, "credit": 0},
                {"account_id": bank_account.gl_account_id, "debit": 0, "credit": amount},
            ]
        )
        entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=transaction_date,
            memo=description,
            source_module=JournalSourceModule.BANK,
            lines=lines,
            created_by_user_id=created_by_user_id,
        )

        txn = await self.txn_repo.create(
            bank_account_id=bank_account_id,
            journal_entry_id=entry.id,
            transaction_date=transaction_date,
            description=description,
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            reference_number=reference_number,
            source=BankTransactionSource.MANUAL,
        )
        logger.info("bank_transaction_recorded", transaction_id=str(txn.id))
        return txn

    async def record_linked_transaction(
        self,
        bank_account_id: uuid.UUID,
        journal_entry_id: uuid.UUID,
        transaction_date: datetime,
        description: str,
        debit_amount: float,
        credit_amount: float,
        source: BankTransactionSource,
        source_id: uuid.UUID,
        reference_number: str | None = None,
    ) -> BankTransaction:
        """Called by Receipts/Payments (which already posted their own journal entry)."""
        return await self.txn_repo.create(
            bank_account_id=bank_account_id,
            journal_entry_id=journal_entry_id,
            transaction_date=transaction_date,
            description=description,
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            reference_number=reference_number,
            source=source,
            source_id=source_id,
        )

    async def list_transactions(self, bank_account_id: uuid.UUID, **filters):
        return await self.txn_repo.list_for_account(bank_account_id, **filters)

    async def reconcile_transaction(self, transaction_id: uuid.UUID) -> BankTransaction:
        txn = await self.txn_repo.get_by_id(transaction_id)
        if not txn:
            raise NotFoundError("Bank transaction", transaction_id)
        if txn.is_reconciled:
            raise ValidationError("This transaction is already reconciled.")
        reconciled = await self.txn_repo.mark_reconciled(txn, datetime.now(timezone.utc))
        logger.info("bank_transaction_reconciled", transaction_id=str(transaction_id))
        return reconciled
