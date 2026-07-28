import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.payments.models import PaymentStatus
from modules.accounting.payments.schemas import MessageResponse, PaymentCreateRequest, PaymentPublic
from modules.accounting.payments.service import PaymentService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=PaymentPublic, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.payments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PaymentService(db)
    payment = await service.create_payment(
        organization_id, created_by_user_id=user.id, **payload.model_dump()
    )
    return PaymentPublic.model_validate(payment)


@router.get("", response_model=dict)
async def list_payments(
    vendor_id: uuid.UUID | None = None,
    expense_id: uuid.UUID | None = None,
    status_filter: PaymentStatus | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.payments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PaymentService(db)
    payments, total = await service.list_payments(
        organization_id,
        vendor_id=vendor_id,
        expense_id=expense_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [PaymentPublic.model_validate(p) for p in payments],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{payment_id}", response_model=PaymentPublic)
async def get_payment(
    payment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.payments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PaymentService(db)
    payment = await service.get_payment(payment_id, organization_id)
    return PaymentPublic.model_validate(payment)


@router.post("/{payment_id}/void", response_model=PaymentPublic)
async def void_payment(
    payment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.payments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PaymentService(db)
    payment = await service.void_payment(payment_id, organization_id)
    return PaymentPublic.model_validate(payment)
