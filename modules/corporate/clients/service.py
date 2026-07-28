import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.accounting.customers.repository import CustomerRepository
from modules.corporate.clients.models import Client
from modules.corporate.clients.repository import ClientRepository

logger = get_logger(__name__)


class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ClientRepository(db)
        self.customer_repo = CustomerRepository(db)

    async def create_client(self, organization_id: uuid.UUID, client_code: str, **fields) -> Client:
        existing = await self.repo.get_by_code(organization_id, client_code)
        if existing:
            raise ConflictError(f"A client with code '{client_code}' already exists.")
        if fields.get("accounting_customer_id") is not None:
            customer = await self.customer_repo.get_by_id(fields["accounting_customer_id"], organization_id)
            if not customer:
                raise NotFoundError("Accounting customer", fields["accounting_customer_id"])

        client = await self.repo.create(organization_id=organization_id, client_code=client_code, **fields)
        logger.info("corporate_client_created", client_id=str(client.id))
        return client

    async def get_client(self, client_id: uuid.UUID, organization_id: uuid.UUID) -> Client:
        client = await self.repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        return client

    async def list_clients(self, organization_id: uuid.UUID, **filters) -> tuple[list[Client], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_client(self, client_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Client:
        client = await self.get_client(client_id, organization_id)
        if fields.get("accounting_customer_id") is not None:
            customer = await self.customer_repo.get_by_id(fields["accounting_customer_id"], organization_id)
            if not customer:
                raise NotFoundError("Accounting customer", fields["accounting_customer_id"])
        updated = await self.repo.update(client, **fields)
        logger.info("corporate_client_updated", client_id=str(client_id))
        return updated

    async def change_status(self, client_id: uuid.UUID, organization_id: uuid.UUID, status) -> Client:
        client = await self.get_client(client_id, organization_id)
        updated = await self.repo.update(client, status=status)
        logger.info("corporate_client_status_changed", client_id=str(client_id), status=status.value)
        return updated

    async def delete_client(self, client_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        client = await self.get_client(client_id, organization_id)
        await self.repo.soft_delete(client)
        logger.info("corporate_client_deleted", client_id=str(client_id))
