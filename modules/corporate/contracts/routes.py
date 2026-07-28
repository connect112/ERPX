import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.contracts.models import ContractStatus
from modules.corporate.contracts.schemas import (
    ContractActivateRequest,
    ContractCreateRequest,
    ContractPublic,
    ContractRenewRequest,
    ContractUpdateRequest,
    MessageResponse,
)
from modules.corporate.clients.dependencies import get_current_client
from modules.corporate.clients.models import Client
from modules.corporate.contracts.service import ContractService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=list[ContractPublic])
async def list_my_contracts(
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contracts, _total = await service.list_contracts(
        client.organization_id, client_id=client.id, skip=0, limit=200
    )
    return [ContractPublic.model_validate(c) for c in contracts]


@router.post("", response_model=ContractPublic, status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: ContractCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contract = await service.create_contract(organization_id, **payload.model_dump())
    return ContractPublic.model_validate(contract)


@router.get("", response_model=dict)
async def list_contracts(
    client_id: uuid.UUID | None = None,
    status_filter: ContractStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contracts, total = await service.list_contracts(
        organization_id, client_id=client_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [ContractPublic.model_validate(c) for c in contracts],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/expiring", response_model=list[ContractPublic])
async def list_expiring_contracts(
    within_days: int = Query(default=30, ge=1, le=365),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contracts = await service.list_expiring_contracts(organization_id, within_days)
    return [ContractPublic.model_validate(c) for c in contracts]


@router.get("/{contract_id}", response_model=ContractPublic)
async def get_contract(
    contract_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contract = await service.get_contract(contract_id, organization_id)
    return ContractPublic.model_validate(contract)


@router.patch("/{contract_id}", response_model=ContractPublic)
async def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contract = await service.update_contract(contract_id, organization_id, **payload.model_dump(exclude_unset=True))
    return ContractPublic.model_validate(contract)


@router.post("/{contract_id}/activate", response_model=ContractPublic)
async def activate_contract(
    contract_id: uuid.UUID,
    payload: ContractActivateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contract = await service.activate_contract(contract_id, organization_id, payload.signed_date)
    return ContractPublic.model_validate(contract)


@router.post("/{contract_id}/terminate", response_model=ContractPublic)
async def terminate_contract(
    contract_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contract = await service.terminate_contract(contract_id, organization_id)
    return ContractPublic.model_validate(contract)


@router.post("/{contract_id}/renew", response_model=ContractPublic)
async def renew_contract(
    contract_id: uuid.UUID,
    payload: ContractRenewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contract = await service.renew_contract(contract_id, organization_id, **payload.model_dump())
    return ContractPublic.model_validate(contract)


@router.post("/{contract_id}/mark-expired", response_model=ContractPublic)
async def mark_contract_expired(
    contract_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.contracts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ContractService(db)
    contract = await service.mark_expired(contract_id, organization_id)
    return ContractPublic.model_validate(contract)
