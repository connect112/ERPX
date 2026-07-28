import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.inventory.schemas import (
    AdjustStockRequest,
    InventoryItemCreateRequest,
    InventoryItemPublic,
    InventoryItemUpdateRequest,
    IssueStockRequest,
    ItemCategoryCreateRequest,
    ItemCategoryPublic,
    ItemCategoryUpdateRequest,
    LowStockItemResponse,
    MessageResponse,
    ReceiveStockRequest,
    StockLevelResponse,
    StockTransactionPublic,
    TransferStockRequest,
    WarehouseCreateRequest,
    WarehousePublic,
    WarehouseUpdateRequest,
)
from modules.inventory.service import (
    InventoryItemService,
    ItemCategoryService,
    StockService,
    WarehouseService,
)
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Item Categories ----


@router.post("/categories", response_model=ItemCategoryPublic, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: ItemCategoryCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.items.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ItemCategoryService(db)
    category = await service.create_category(organization_id, **payload.model_dump())
    return ItemCategoryPublic.model_validate(category)


@router.get("/categories", response_model=list[ItemCategoryPublic])
async def list_categories(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.items.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ItemCategoryService(db)
    categories = await service.list_categories(organization_id, is_active)
    return [ItemCategoryPublic.model_validate(c) for c in categories]


@router.patch("/categories/{category_id}", response_model=ItemCategoryPublic)
async def update_category(
    category_id: uuid.UUID,
    payload: ItemCategoryUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.items.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ItemCategoryService(db)
    category = await service.update_category(
        category_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return ItemCategoryPublic.model_validate(category)


# ---- Warehouses ----


@router.post("/warehouses", response_model=WarehousePublic, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    payload: WarehouseCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.warehouses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WarehouseService(db)
    warehouse = await service.create_warehouse(organization_id, **payload.model_dump())
    return WarehousePublic.model_validate(warehouse)


@router.get("/warehouses", response_model=list[WarehousePublic])
async def list_warehouses(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.warehouses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WarehouseService(db)
    warehouses = await service.list_warehouses(organization_id, is_active)
    return [WarehousePublic.model_validate(w) for w in warehouses]


@router.patch("/warehouses/{warehouse_id}", response_model=WarehousePublic)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.warehouses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WarehouseService(db)
    warehouse = await service.update_warehouse(
        warehouse_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return WarehousePublic.model_validate(warehouse)


# ---- Items ----


@router.post("/items", response_model=InventoryItemPublic, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: InventoryItemCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.items.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryItemService(db)
    item = await service.create_item(organization_id, **payload.model_dump())
    return InventoryItemPublic.model_validate(item)


@router.get("/items", response_model=dict)
async def list_items(
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.items.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryItemService(db)
    items, total = await service.list_items(
        organization_id, category_id=category_id, is_active=is_active, search=search, skip=skip, limit=limit
    )
    return {
        "items": [InventoryItemPublic.model_validate(i) for i in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/items/{item_id}", response_model=InventoryItemPublic)
async def get_item(
    item_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.items.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryItemService(db)
    item = await service.get_item(item_id, organization_id)
    return InventoryItemPublic.model_validate(item)


@router.patch("/items/{item_id}", response_model=InventoryItemPublic)
async def update_item(
    item_id: uuid.UUID,
    payload: InventoryItemUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.items.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryItemService(db)
    item = await service.update_item(item_id, organization_id, **payload.model_dump(exclude_unset=True))
    return InventoryItemPublic.model_validate(item)


@router.get("/items/{item_id}/stock-level", response_model=StockLevelResponse)
async def get_stock_level(
    item_id: uuid.UUID,
    warehouse_id: uuid.UUID | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.stock.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StockService(db)
    level = await service.get_stock_level(organization_id, item_id, warehouse_id)
    return StockLevelResponse(**level)


@router.get("/items/{item_id}/transactions", response_model=dict)
async def list_item_transactions(
    item_id: uuid.UUID,
    warehouse_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_permissions("inventory.stock.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StockService(db)
    transactions, total = await service.list_transactions(
        item_id, warehouse_id=warehouse_id, skip=skip, limit=limit
    )
    return {
        "items": [StockTransactionPublic.model_validate(t) for t in transactions],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/low-stock", response_model=list[LowStockItemResponse])
async def list_low_stock_items(
    warehouse_id: uuid.UUID | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.stock.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StockService(db)
    low_stock = await service.list_low_stock_items(organization_id, warehouse_id)
    return [LowStockItemResponse(**i) for i in low_stock]


# ---- Stock Movements ----


@router.post("/stock/receive", response_model=StockTransactionPublic, status_code=status.HTTP_201_CREATED)
async def receive_stock(
    payload: ReceiveStockRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.stock.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StockService(db)
    transaction = await service.receive_stock(organization_id, created_by_user_id=user.id, **payload.model_dump())
    return StockTransactionPublic.model_validate(transaction)


@router.post("/stock/issue", response_model=StockTransactionPublic, status_code=status.HTTP_201_CREATED)
async def issue_stock(
    payload: IssueStockRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.stock.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StockService(db)
    transaction = await service.issue_stock(organization_id, created_by_user_id=user.id, **payload.model_dump())
    return StockTransactionPublic.model_validate(transaction)


@router.post("/stock/adjust", response_model=StockTransactionPublic, status_code=status.HTTP_201_CREATED)
async def adjust_stock(
    payload: AdjustStockRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.stock.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StockService(db)
    transaction = await service.adjust_stock(organization_id, created_by_user_id=user.id, **payload.model_dump())
    return StockTransactionPublic.model_validate(transaction)


@router.post("/stock/transfer", response_model=list[StockTransactionPublic], status_code=status.HTTP_201_CREATED)
async def transfer_stock(
    payload: TransferStockRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("inventory.stock.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StockService(db)
    out_txn, in_txn = await service.transfer_stock(organization_id, created_by_user_id=user.id, **payload.model_dump())
    return [StockTransactionPublic.model_validate(out_txn), StockTransactionPublic.model_validate(in_txn)]
