import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.quotations.models import QuotationStatus
from modules.corporate.quotations.schemas import (
    MessageResponse,
    QuotationCreateRequest,
    QuotationPublic,
    QuotationRejectRequest,
    QuotationUpdateRequest,
)
from modules.corporate.quotations.service import QuotationService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=QuotationPublic, status_code=status.HTTP_201_CREATED)
async def create_quotation(
    payload: QuotationCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.quotations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuotationService(db)
    data = payload.model_dump()
    lines = data.pop("lines")
    quotation = await service.create_quotation(organization_id, lines=lines, **data)
    return QuotationPublic.model_validate(quotation)


@router.get("", response_model=dict)
async def list_quotations(
    client_id: uuid.UUID | None = None,
    status_filter: QuotationStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.quotations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = QuotationService(db)
    quotations, total = await service.list_quotations(
        organization_id, client_id=client_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [QuotationPublic.model_validate(q) for q in quotations],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{quotation_id}", response_model=QuotationPublic)
async def get_quotation(
    quotation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.quotations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = QuotationService(db)
    quotation = await service.get_quotation(quotation_id, organization_id)
    return QuotationPublic.model_validate(quotation)


@router.patch("/{quotation_id}", response_model=QuotationPublic)
async def update_quotation(
    quotation_id: uuid.UUID,
    payload: QuotationUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.quotations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuotationService(db)
    data = payload.model_dump(exclude_unset=True)
    lines = data.pop("lines", None)
    quotation = await service.update_quotation(quotation_id, organization_id, lines=lines, **data)
    return QuotationPublic.model_validate(quotation)


@router.post("/{quotation_id}/send", response_model=QuotationPublic)
async def send_quotation(
    quotation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.quotations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuotationService(db)
    quotation = await service.send_quotation(quotation_id, organization_id)
    return QuotationPublic.model_validate(quotation)


@router.post("/{quotation_id}/accept", response_model=QuotationPublic)
async def accept_quotation(
    quotation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.quotations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuotationService(db)
    quotation = await service.accept_quotation(quotation_id, organization_id)
    return QuotationPublic.model_validate(quotation)


@router.post("/{quotation_id}/reject", response_model=QuotationPublic)
async def reject_quotation(
    quotation_id: uuid.UUID,
    payload: QuotationRejectRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.quotations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuotationService(db)
    quotation = await service.reject_quotation(quotation_id, organization_id, payload.rejection_reason)
    return QuotationPublic.model_validate(quotation)
