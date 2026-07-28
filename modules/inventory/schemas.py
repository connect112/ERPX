import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.inventory.models import StockTransactionType


class ItemCategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    description: str | None = None


class ItemCategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class ItemCategoryPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WarehouseCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    branch_id: uuid.UUID | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None


class WarehouseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    is_active: bool | None = None


class WarehousePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    name: str
    code: str
    address_line1: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryItemCreateRequest(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    category_id: uuid.UUID | None = None
    description: str | None = None
    unit_of_measure: str = Field(..., min_length=1, max_length=20)
    reorder_level: float = Field(default=0, ge=0)
    reorder_quantity: float = Field(default=0, ge=0)
    standard_cost: float = Field(default=0, ge=0)


class InventoryItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    category_id: uuid.UUID | None = None
    description: str | None = None
    unit_of_measure: str | None = None
    reorder_level: float | None = Field(default=None, ge=0)
    reorder_quantity: float | None = Field(default=None, ge=0)
    standard_cost: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class InventoryItemPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    category_id: uuid.UUID | None
    sku: str
    name: str
    description: str | None
    unit_of_measure: str
    reorder_level: float
    reorder_quantity: float
    standard_cost: float
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiveStockRequest(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: float = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)
    transaction_date: datetime | None = None
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    notes: str | None = None


class IssueStockRequest(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: float = Field(..., gt=0)
    transaction_date: datetime | None = None
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    notes: str | None = None


class AdjustStockRequest(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity_change: float = Field(..., description="Positive to increase stock, negative to decrease it.")
    unit_cost: float = Field(default=0, ge=0)
    reason: str = Field(..., min_length=2)


class TransferStockRequest(BaseModel):
    item_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    quantity: float = Field(..., gt=0)
    notes: str | None = None


class StockTransactionPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    warehouse_id: uuid.UUID
    item_id: uuid.UUID
    transaction_type: StockTransactionType
    quantity: float
    unit_cost: float
    transaction_date: datetime
    reference_type: str | None
    reference_id: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StockLevelResponse(BaseModel):
    item_id: uuid.UUID
    warehouse_id: uuid.UUID | None
    quantity_on_hand: float
    average_unit_cost: float
    stock_value: float


class LowStockItemResponse(BaseModel):
    item_id: uuid.UUID
    sku: str
    name: str
    reorder_level: float
    quantity_on_hand: float


class MessageResponse(BaseModel):
    message: str
