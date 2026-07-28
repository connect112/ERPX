import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.integrations.schemas import (
    IntegrationCreateRequest,
    IntegrationListResponse,
    IntegrationPublic,
    IntegrationUpdateRequest,
    MessageResponse,
)
from modules.integrations.service import IntegrationService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=IntegrationPublic, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("integrations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationService(db)
    integration = await service.create_integration(organization_id, user.id, **payload.model_dump())
    return IntegrationPublic.from_model(integration)


@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("integrations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationService(db)
    integrations, total = await service.list_integrations(organization_id, skip=skip, limit=limit)
    return IntegrationListResponse(
        items=[IntegrationPublic.from_model(i) for i in integrations], total=total
    )


@router.get("/{integration_id}", response_model=IntegrationPublic)
async def get_integration(
    integration_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("integrations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationService(db)
    integration = await service.get_integration(integration_id, organization_id)
    return IntegrationPublic.from_model(integration)


@router.patch("/{integration_id}", response_model=IntegrationPublic)
async def update_integration(
    integration_id: uuid.UUID,
    payload: IntegrationUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("integrations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationService(db)
    integration = await service.update_integration(
        integration_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return IntegrationPublic.from_model(integration)


@router.delete("/{integration_id}", response_model=MessageResponse)
async def delete_integration(
    integration_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("integrations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationService(db)
    await service.delete_integration(integration_id, organization_id)
    return MessageResponse(message="Integration deleted successfully.")


@router.post("/{integration_id}/test", response_model=IntegrationPublic)
async def test_integration(
    integration_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("integrations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationService(db)
    integration = await service.test_connection(integration_id, organization_id)
    return IntegrationPublic.from_model(integration)
