import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.ledger.models import Account, AccountType


class AccountRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Account:
        account = Account(**fields)
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def get_by_id(self, account_id: uuid.UUID, organization_id: uuid.UUID) -> Account | None:
        result = await self.db.execute(
            select(Account).where(
                Account.id == account_id, Account.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> Account | None:
        result = await self.db.execute(
            select(Account).where(Account.organization_id == organization_id, Account.code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        account_type: AccountType | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Account], int]:
        conditions = [Account.organization_id == organization_id]
        if account_type is not None:
            conditions.append(Account.account_type == account_type)
        if is_active is not None:
            conditions.append(Account.is_active == is_active)
        if search:
            like_pattern = f"%{search}%"
            conditions.append((Account.code.ilike(like_pattern)) | (Account.name.ilike(like_pattern)))

        count_result = await self.db.execute(select(func.count()).select_from(Account).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Account).where(*conditions).order_by(Account.code.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_children(self, parent_account_id: uuid.UUID) -> list[Account]:
        result = await self.db.execute(
            select(Account).where(Account.parent_account_id == parent_account_id)
        )
        return list(result.scalars().all())

    async def update(self, account: Account, **fields) -> Account:
        for key, value in fields.items():
            if value is not None:
                setattr(account, key, value)
        await self.db.flush()
        await self.db.refresh(account)
        return account
