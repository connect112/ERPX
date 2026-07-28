import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.procurement.models import PurchaseOrderStatus
from modules.procurement.schemas import (
    GoodsReceiptCreateRequest,
    GoodsReceiptPublic,
    MessageResponse,
    PurchaseOrderCreateRequest,
    PurchaseOrderPublic,
    PurchaseOrderUpdateRequest,
)
from modules.procurement.service import GoodsReceiptService, PurchaseOrderService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Purchase Orders ----


@router.post("/purchase-orders", response_model=PurchaseOrderPublic, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    payload: PurchaseOrderCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.purchase_orders.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PurchaseOrderService(db)
    data = payload.model_dump()
    lines = data.pop("lines")
    po = await service.create_purchase_order(organization_id, lines=lines, created_by_user_id=user.id, **data)
    return PurchaseOrderPublic.model_validate(po)


@router.get("/purchase-orders", response_model=dict)
async def list_purchase_orders(
    vendor_id: uuid.UUID | None = None,
    status_filter: PurchaseOrderStatus | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.purchase_orders.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PurchaseOrderService(db)
    orders, total = await service.list_purchase_orders(
        organization_id, vendor_id=vendor_id, status=status_filter, date_from=date_from, date_to=date_to, skip=skip, limit=limit
    )
    return {
        "items": [PurchaseOrderPublic.model_validate(o) for o in orders],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderPublic)
async def get_purchase_order(
    po_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.purchase_orders.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PurchaseOrderService(db)
    po = await service.get_purchase_order(po_id, organization_id)
    return PurchaseOrderPublic.model_validate(po)


@router.patch("/purchase-orders/{po_id}", response_model=PurchaseOrderPublic)
async def update_purchase_order(
    po_id: uuid.UUID,
    payload: PurchaseOrderUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.purchase_orders.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PurchaseOrderService(db)
    data = payload.model_dump(exclude_unset=True)
    lines = data.pop("lines", None)
    po = await service.update_purchase_order(po_id, organization_id, lines=lines, **data)
    return PurchaseOrderPublic.model_validate(po)


@router.post("/purchase-orders/{po_id}/send", response_model=PurchaseOrderPublic)
async def send_purchase_order(
    po_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.purchase_orders.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PurchaseOrderService(db)
    po = await service.send_purchase_order(po_id, organization_id)
    return PurchaseOrderPublic.model_validate(po)


@router.post("/purchase-orders/{po_id}/cancel", response_model=PurchaseOrderPublic)
async def cancel_purchase_order(
    po_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.purchase_orders.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PurchaseOrderService(db)
    po = await service.cancel_purchase_order(po_id, organization_id)
    return PurchaseOrderPublic.model_validate(po)


# ---- Goods Receipts ----


@router.post("/goods-receipts", response_model=GoodsReceiptPublic, status_code=status.HTTP_201_CREATED)
async def receive_goods(
    payload: GoodsReceiptCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.goods_receipts.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = GoodsReceiptService(db)
    data = payload.model_dump()
    lines = data.pop("lines")
    receipt = await service.receive_goods(organization_id, lines=lines, received_by_user_id=user.id, **data)
    return GoodsReceiptPublic.model_validate(receipt)


@router.get("/goods-receipts/{receipt_id}", response_model=GoodsReceiptPublic)
async def get_goods_receipt(
    receipt_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.goods_receipts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = GoodsReceiptService(db)
    receipt = await service.get_receipt(receipt_id, organization_id)
    return GoodsReceiptPublic.model_validate(receipt)


@router.get("/purchase-orders/{po_id}/goods-receipts", response_model=list[GoodsReceiptPublic])
async def list_goods_receipts_for_po(
    po_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("procurement.goods_receipts.view")),
    db: AsyncSession = Depends(get_db),
):
    service = GoodsReceiptService(db)
    receipts = await service.list_for_purchase_order(po_id, organization_id)
    return [GoodsReceiptPublic.model_validate(r) for r in receipts]
