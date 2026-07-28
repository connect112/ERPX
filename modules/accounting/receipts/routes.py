import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.receipts.models import ReceiptStatus
from modules.accounting.receipts.schemas import MessageResponse, ReceiptCreateRequest, ReceiptPublic
from modules.accounting.receipts.service import ReceiptService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=ReceiptPublic, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    payload: ReceiptCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.receipts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.create_receipt(
        organization_id, created_by_user_id=user.id, **payload.model_dump()
    )
    return ReceiptPublic.model_validate(receipt)


@router.get("", response_model=dict)
async def list_receipts(
    customer_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    status_filter: ReceiptStatus | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.receipts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipts, total = await service.list_receipts(
        organization_id,
        customer_id=customer_id,
        invoice_id=invoice_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [ReceiptPublic.model_validate(r) for r in receipts],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{receipt_id}", response_model=ReceiptPublic)
async def get_receipt(
    receipt_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.receipts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.get_receipt(receipt_id, organization_id)
    return ReceiptPublic.model_validate(receipt)


@router.post("/{receipt_id}/void", response_model=ReceiptPublic)
async def void_receipt(
    receipt_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.receipts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.void_receipt(receipt_id, organization_id)
    return ReceiptPublic.model_validate(receipt)
