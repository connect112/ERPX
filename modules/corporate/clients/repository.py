import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.corporate.clients.models import Client, ClientStatus


class ClientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Client:
        client = Client(**fields)
        self.db.add(client)
        await self.db.flush()
        await self.db.refresh(client)
        return client

    async def get_by_id(self, client_id: uuid.UUID, organization_id: uuid.UUID) -> Client | None:
        result = await self.db.execute(
            select(Client).where(
                Client.id == client_id, Client.organization_id == organization_id, Client.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, client_code: str) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.organization_id == organization_id, Client.client_code == client_code)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.user_id == user_id, Client.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: ClientStatus | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Client], int]:
        conditions = [Client.organization_id == organization_id, Client.deleted_at.is_(None)]
        if status is not None:
            conditions.append(Client.status == status)
        if search:
            like_pattern = f"%{search}%"
            conditions.append(
                (Client.name.ilike(like_pattern))
                | (Client.client_code.ilike(like_pattern))
                | (Client.contact_email.ilike(like_pattern))
            )

        count_result = await self.db.execute(select(func.count()).select_from(Client).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Client).where(*conditions).order_by(Client.name.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, client: Client, **fields) -> Client:
        for key, value in fields.items():
            if value is not None:
                setattr(client, key, value)
        await self.db.flush()
        await self.db.refresh(client)
        return client

    async def soft_delete(self, client: Client) -> None:
        from datetime import datetime, timezone

        client.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
