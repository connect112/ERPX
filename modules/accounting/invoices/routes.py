import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.invoices.models import InvoiceStatus
from modules.accounting.invoices.schemas import (
    InvoiceCreateRequest,
    InvoicePublic,
    InvoiceUpdateRequest,
    MessageResponse,
)
from modules.accounting.invoices.service import InvoiceService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=InvoicePublic, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.invoices.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InvoiceService(db)
    data = payload.model_dump()
    lines = data.pop("lines")
    invoice = await service.create_invoice(organization_id, lines=lines, **data)
    return InvoicePublic.model_validate(invoice)


@router.get("", response_model=dict)
async def list_invoices(
    customer_id: uuid.UUID | None = None,
    status_filter: InvoiceStatus | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.invoices.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InvoiceService(db)
    invoices, total = await service.list_invoices(
        organization_id,
        customer_id=customer_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [InvoicePublic.model_validate(i) for i in invoices],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{invoice_id}", response_model=InvoicePublic)
async def get_invoice(
    invoice_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.invoices.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id, organization_id)
    return InvoicePublic.model_validate(invoice)


@router.patch("/{invoice_id}", response_model=InvoicePublic)
async def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.invoices.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InvoiceService(db)
    data = payload.model_dump(exclude_unset=True)
    lines = data.pop("lines", None)
    invoice = await service.update_invoice(invoice_id, organization_id, lines=lines, **data)
    return InvoicePublic.model_validate(invoice)


@router.post("/{invoice_id}/post", response_model=InvoicePublic)
async def post_invoice(
    invoice_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.invoices.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InvoiceService(db)
    invoice = await service.post_invoice(invoice_id, organization_id, created_by_user_id=user.id)
    return InvoicePublic.model_validate(invoice)


@router.post("/{invoice_id}/cancel", response_model=InvoicePublic)
async def cancel_invoice(
    invoice_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.invoices.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InvoiceService(db)
    invoice = await service.cancel_invoice(invoice_id, organization_id)
    return InvoicePublic.model_validate(invoice)
