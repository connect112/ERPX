import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.bank.models import BankAccount, BankTransaction


class BankAccountRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> BankAccount:
        account = BankAccount(**fields)
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def get_by_id(self, bank_account_id: uuid.UUID, organization_id: uuid.UUID) -> BankAccount | None:
        result = await self.db.execute(
            select(BankAccount).where(
                BankAccount.id == bank_account_id, BankAccount.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[BankAccount]:
        conditions = [BankAccount.organization_id == organization_id]
        if is_active is not None:
            conditions.append(BankAccount.is_active == is_active)
        result = await self.db.execute(
            select(BankAccount).where(*conditions).order_by(BankAccount.account_name.asc())
        )
        return list(result.scalars().all())

    async def update(self, account: BankAccount, **fields) -> BankAccount:
        for key, value in fields.items():
            if value is not None:
                setattr(account, key, value)
        await self.db.flush()
        await self.db.refresh(account)
        return account


class BankTransactionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> BankTransaction:
        txn = BankTransaction(**fields)
        self.db.add(txn)
        await self.db.flush()
        await self.db.refresh(txn)
        return txn

    async def get_by_id(self, transaction_id: uuid.UUID) -> BankTransaction | None:
        result = await self.db.execute(
            select(BankTransaction).where(BankTransaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def list_for_account(
        self,
        bank_account_id: uuid.UUID,
        is_reconciled: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[BankTransaction], int]:
        conditions = [BankTransaction.bank_account_id == bank_account_id]
        if is_reconciled is not None:
            conditions.append(BankTransaction.is_reconciled == is_reconciled)
        if date_from is not None:
            conditions.append(BankTransaction.transaction_date >= date_from)
        if date_to is not None:
            conditions.append(BankTransaction.transaction_date <= date_to)

        count_result = await self.db.execute(
            select(func.count()).select_from(BankTransaction).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(BankTransaction)
            .where(*conditions)
            .order_by(BankTransaction.transaction_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def sum_for_account(
        self, bank_account_id: uuid.UUID, as_of_date: datetime | None = None
    ) -> tuple[float, float]:
        conditions = [BankTransaction.bank_account_id == bank_account_id]
        if as_of_date is not None:
            conditions.append(BankTransaction.transaction_date <= as_of_date)
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(BankTransaction.debit_amount), 0),
                func.coalesce(func.sum(BankTransaction.credit_amount), 0),
            ).where(*conditions)
        )
        total_debit, total_credit = result.one()
        return float(total_debit), float(total_credit)

    async def mark_reconciled(self, txn: BankTransaction, reconciled_at: datetime) -> BankTransaction:
        txn.is_reconciled = True
        txn.reconciled_at = reconciled_at
        await self.db.flush()
        await self.db.refresh(txn)
        return txn
