import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.accounting.customers.models import Customer


class CustomerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Customer:
        customer = Customer(**fields)
        self.db.add(customer)
        await self.db.flush()
        await self.db.refresh(customer)
        return customer

    async def get_by_id(self, customer_id: uuid.UUID, organization_id: uuid.UUID) -> Customer | None:
        result = await self.db.execute(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.organization_id == organization_id,
                Customer.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, customer_code: str) -> Customer | None:
        result = await self.db.execute(
            select(Customer).where(
                Customer.organization_id == organization_id, Customer.customer_code == customer_code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Customer], int]:
        conditions = [Customer.organization_id == organization_id, Customer.deleted_at.is_(None)]
        if is_active is not None:
            conditions.append(Customer.is_active == is_active)
        if search:
            like_pattern = f"%{search}%"
            conditions.append(
                (Customer.name.ilike(like_pattern))
                | (Customer.customer_code.ilike(like_pattern))
                | (Customer.email.ilike(like_pattern))
            )

        count_result = await self.db.execute(select(func.count()).select_from(Customer).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Customer).where(*conditions).order_by(Customer.name.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, customer: Customer, **fields) -> Customer:
        for key, value in fields.items():
            if value is not None:
                setattr(customer, key, value)
        await self.db.flush()
        await self.db.refresh(customer)
        return customer

    async def soft_delete(self, customer: Customer) -> None:
        from datetime import datetime, timezone

        customer.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
