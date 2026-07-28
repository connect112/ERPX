import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.gst.schemas import (
    GSTRateCreateRequest,
    GSTRatePublic,
    GSTRateUpdateRequest,
    GSTReturnSummaryResponse,
    TaxComputationRequest,
    TaxComputationResponse,
)
from modules.accounting.gst.service import GSTService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/rates", response_model=GSTRatePublic, status_code=status.HTTP_201_CREATED)
async def create_gst_rate(
    payload: GSTRateCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.gst.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = GSTService(db)
    rate = await service.create_rate(organization_id, **payload.model_dump())
    return GSTRatePublic.model_validate(rate)


@router.get("/rates", response_model=list[GSTRatePublic])
async def list_gst_rates(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.gst.view")),
    db: AsyncSession = Depends(get_db),
):
    service = GSTService(db)
    rates = await service.list_rates(organization_id, is_active)
    return [GSTRatePublic.model_validate(r) for r in rates]


@router.patch("/rates/{rate_id}", response_model=GSTRatePublic)
async def update_gst_rate(
    rate_id: uuid.UUID,
    payload: GSTRateUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.gst.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = GSTService(db)
    rate = await service.update_rate(rate_id, organization_id, **payload.model_dump(exclude_unset=True))
    return GSTRatePublic.model_validate(rate)


@router.post("/compute", response_model=TaxComputationResponse)
async def compute_tax(
    payload: TaxComputationRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.gst.view")),
    db: AsyncSession = Depends(get_db),
):
    service = GSTService(db)
    result = await service.compute_tax(organization_id, **payload.model_dump())
    return TaxComputationResponse(**result)


@router.get("/returns/summary", response_model=GSTReturnSummaryResponse)
async def get_return_summary(
    period_from: date = Query(...),
    period_to: date = Query(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.gst.view")),
    db: AsyncSession = Depends(get_db),
):
    service = GSTService(db)
    summary = await service.get_return_summary(organization_id, period_from, period_to)
    return GSTReturnSummaryResponse(**summary)
