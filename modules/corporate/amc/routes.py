import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.amc.models import AMCStatus, AMCVisitStatus
from modules.corporate.amc.schemas import (
    AMCContractCreateRequest,
    AMCContractPublic,
    AMCContractUpdateRequest,
    AMCVisitCompleteRequest,
    AMCVisitCreateRequest,
    AMCVisitPublic,
    MessageResponse,
)
from modules.corporate.amc.service import AMCContractService, AMCVisitService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/contracts", response_model=AMCContractPublic, status_code=status.HTTP_201_CREATED)
async def create_amc_contract(
    payload: AMCContractCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.amc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCContractService(db)
    amc = await service.create_amc_contract(organization_id, **payload.model_dump())
    return AMCContractPublic.model_validate(amc)


@router.get("/contracts", response_model=dict)
async def list_amc_contracts(
    client_id: uuid.UUID | None = None,
    status_filter: AMCStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.amc.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCContractService(db)
    contracts, total = await service.list_amc_contracts(
        organization_id, client_id=client_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [AMCContractPublic.model_validate(c) for c in contracts],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/contracts/due-for-renewal", response_model=list[AMCContractPublic])
async def list_due_for_renewal(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.amc.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCContractService(db)
    contracts = await service.list_due_for_renewal(organization_id)
    return [AMCContractPublic.model_validate(c) for c in contracts]


@router.get("/contracts/{amc_contract_id}", response_model=AMCContractPublic)
async def get_amc_contract(
    amc_contract_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.amc.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCContractService(db)
    amc = await service.get_amc_contract(amc_contract_id, organization_id)
    return AMCContractPublic.model_validate(amc)


@router.patch("/contracts/{amc_contract_id}", response_model=AMCContractPublic)
async def update_amc_contract(
    amc_contract_id: uuid.UUID,
    payload: AMCContractUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.amc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCContractService(db)
    amc = await service.update_amc_contract(amc_contract_id, organization_id, **payload.model_dump(exclude_unset=True))
    return AMCContractPublic.model_validate(amc)


@router.post("/contracts/{amc_contract_id}/visits", response_model=AMCVisitPublic, status_code=status.HTTP_201_CREATED)
async def schedule_visit(
    amc_contract_id: uuid.UUID,
    payload: AMCVisitCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.amc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCVisitService(db)
    visit = await service.schedule_visit(amc_contract_id, organization_id, **payload.model_dump())
    return AMCVisitPublic.model_validate(visit)


@router.get("/contracts/{amc_contract_id}/visits", response_model=list[AMCVisitPublic])
async def list_visits(
    amc_contract_id: uuid.UUID,
    status_filter: AMCVisitStatus | None = Query(default=None, alias="status"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.amc.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCVisitService(db)
    visits = await service.list_visits(amc_contract_id, organization_id, status_filter)
    return [AMCVisitPublic.model_validate(v) for v in visits]


@router.post("/visits/{visit_id}/complete", response_model=AMCVisitPublic)
async def complete_visit(
    visit_id: uuid.UUID,
    payload: AMCVisitCompleteRequest,
    user: User = Depends(require_permissions("corporate.amc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCVisitService(db)
    visit = await service.complete_visit(visit_id, payload.findings)
    return AMCVisitPublic.model_validate(visit)


@router.post("/visits/{visit_id}/cancel", response_model=AMCVisitPublic)
async def cancel_visit(
    visit_id: uuid.UUID,
    user: User = Depends(require_permissions("corporate.amc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AMCVisitService(db)
    visit = await service.cancel_visit(visit_id)
    return AMCVisitPublic.model_validate(visit)
