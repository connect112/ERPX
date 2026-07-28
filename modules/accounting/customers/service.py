import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.accounting.customers.models import Customer
from modules.accounting.customers.repository import CustomerRepository

logger = get_logger(__name__)


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CustomerRepository(db)

    async def create_customer(self, organization_id: uuid.UUID, customer_code: str, **fields) -> Customer:
        existing = await self.repo.get_by_code(organization_id, customer_code)
        if existing:
            raise ConflictError(f"A customer with code '{customer_code}' already exists.")
        customer = await self.repo.create(
            organization_id=organization_id, customer_code=customer_code, **fields
        )
        logger.info("customer_created", customer_id=str(customer.id))
        return customer

    async def get_customer(self, customer_id: uuid.UUID, organization_id: uuid.UUID) -> Customer:
        customer = await self.repo.get_by_id(customer_id, organization_id)
        if not customer:
            raise NotFoundError("Customer", customer_id)
        return customer

    async def list_customers(self, organization_id: uuid.UUID, **filters) -> tuple[list[Customer], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_customer(
        self, customer_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Customer:
        customer = await self.get_customer(customer_id, organization_id)
        updated = await self.repo.update(customer, **fields)
        logger.info("customer_updated", customer_id=str(customer_id))
        return updated

    async def delete_customer(self, customer_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        customer = await self.get_customer(customer_id, organization_id)
        await self.repo.soft_delete(customer)
        logger.info("customer_deleted", customer_id=str(customer_id))
