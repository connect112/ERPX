import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.procurement.models import PurchaseOrderStatus


class PurchaseOrderLineRequest(BaseModel):
    item_id: uuid.UUID
    description: str = Field(..., min_length=1, max_length=500)
    quantity_ordered: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    gst_rate_id: uuid.UUID | None = None


class PurchaseOrderCreateRequest(BaseModel):
    vendor_id: uuid.UUID
    po_number: str = Field(..., min_length=1, max_length=50)
    order_date: datetime
    expected_delivery_date: datetime | None = None
    branch_id: uuid.UUID | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineRequest] = Field(..., min_length=1)


class PurchaseOrderUpdateRequest(BaseModel):
    expected_delivery_date: datetime | None = None
    notes: str | None = None
    lines: list[PurchaseOrderLineRequest] | None = None


class PurchaseOrderLinePublic(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    gst_rate_id: uuid.UUID | None
    description: str
    quantity_ordered: float
    quantity_received: float
    unit_price: float
    line_subtotal: float
    tax_amount: float
    line_total: float

    model_config = {"from_attributes": True}


class PurchaseOrderPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    vendor_id: uuid.UUID
    po_number: str
    order_date: datetime
    expected_delivery_date: datetime | None
    status: PurchaseOrderStatus
    subtotal_amount: float
    tax_amount: float
    total_amount: float
    notes: str | None
    created_at: datetime
    lines: list[PurchaseOrderLinePublic] = []

    model_config = {"from_attributes": True}


class GoodsReceiptLineRequest(BaseModel):
    purchase_order_line_id: uuid.UUID
    quantity_received: float = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)


class GoodsReceiptCreateRequest(BaseModel):
    purchase_order_id: uuid.UUID
    warehouse_id: uuid.UUID
    receipt_number: str = Field(..., min_length=1, max_length=50)
    receipt_date: datetime
    notes: str | None = None
    lines: list[GoodsReceiptLineRequest] = Field(..., min_length=1)


class GoodsReceiptLinePublic(BaseModel):
    id: uuid.UUID
    purchase_order_line_id: uuid.UUID
    quantity_received: float
    unit_cost: float

    model_config = {"from_attributes": True}


class GoodsReceiptPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    purchase_order_id: uuid.UUID
    warehouse_id: uuid.UUID
    received_by_user_id: uuid.UUID | None
    receipt_number: str
    receipt_date: datetime
    notes: str | None
    created_at: datetime
    lines: list[GoodsReceiptLinePublic] = []

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
