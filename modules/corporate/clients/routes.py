import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.clients.models import ClientStatus
from modules.corporate.clients.schemas import (
    ClientCreateRequest,
    ClientPublic,
    ClientStatusChangeRequest,
    ClientUpdateRequest,
    MessageResponse,
)
from modules.corporate.clients.dependencies import get_current_client
from modules.corporate.clients.service import ClientService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=ClientPublic)
async def get_my_client_profile(client=Depends(get_current_client)):
    return ClientPublic.model_validate(client)


@router.post("", response_model=ClientPublic, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.clients.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    client = await service.create_client(organization_id, **payload.model_dump())
    return ClientPublic.model_validate(client)


@router.get("", response_model=dict)
async def list_clients(
    status_filter: ClientStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.clients.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    clients, total = await service.list_clients(
        organization_id, status=status_filter, search=search, skip=skip, limit=limit
    )
    return {
        "items": [ClientPublic.model_validate(c) for c in clients],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{client_id}", response_model=ClientPublic)
async def get_client(
    client_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.clients.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    client = await service.get_client(client_id, organization_id)
    return ClientPublic.model_validate(client)


@router.patch("/{client_id}", response_model=ClientPublic)
async def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.clients.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    client = await service.update_client(client_id, organization_id, **payload.model_dump(exclude_unset=True))
    return ClientPublic.model_validate(client)


@router.post("/{client_id}/status", response_model=ClientPublic)
async def change_client_status(
    client_id: uuid.UUID,
    payload: ClientStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.clients.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    client = await service.change_status(client_id, organization_id, payload.status)
    return ClientPublic.model_validate(client)


@router.delete("/{client_id}", response_model=MessageResponse)
async def delete_client(
    client_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.clients.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    await service.delete_client(client_id, organization_id)
    return MessageResponse(message="Client deleted successfully.")
