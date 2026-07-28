"""
Corporate Clients module — FastAPI dependencies.

`get_current_client` is what every self-service "me" endpoint (corporate
portal: my tickets, my projects, my contracts, ...) depends on instead of
an RBAC permission check — a client contact doesn't need `tickets.view`
to see their *own* organization's tickets; owning the record is the
authorization. `Client.user_id` is the client-portal login, distinct from
`account_manager_user_id` (the internal staff member who manages them).
"""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.corporate.clients.models import Client
from modules.corporate.clients.repository import ClientRepository


async def get_current_client(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Client:
    client = await ClientRepository(db).get_by_user_id(user.id)
    if not client:
        raise ValidationError(
            "Your account is not linked to a client record. Contact your administrator."
        )
    return client


async def get_current_client_organization_id(
    client: Client = Depends(get_current_client),
) -> uuid.UUID:
    return client.organization_id
