import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.branches.models import Branch


class BranchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_for_organization(self, organization_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Branch).where(Branch.organization_id == organization_id)
        )
        return result.scalar_one()

    async def create(self, **fields) -> Branch:
        branch = Branch(**fields)
        self.db.add(branch)
        await self.db.flush()
        await self.db.refresh(branch)
        return branch

    async def get_by_id(self, branch_id: uuid.UUID) -> Branch | None:
        result = await self.db.execute(select(Branch).where(Branch.id == branch_id))
        return result.scalar_one_or_none()

    async def get_by_org_and_code(self, organization_id: uuid.UUID, code: str) -> Branch | None:
        result = await self.db.execute(
            select(Branch).where(Branch.organization_id == organization_id, Branch.code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Branch]:
        result = await self.db.execute(
            select(Branch).where(Branch.organization_id == organization_id).order_by(Branch.name)
        )
        return list(result.scalars().all())

    async def update(self, branch: Branch, **fields) -> Branch:
        for key, value in fields.items():
            if value is not None:
                setattr(branch, key, value)
        await self.db.flush()
        return branch

    async def delete(self, branch: Branch) -> None:
        await self.db.delete(branch)
        await self.db.flush()
