import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.inventory.models import InventoryItem, ItemCategory, StockTransaction, Warehouse


class ItemCategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ItemCategory:
        category = ItemCategory(**fields)
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def get_by_id(self, category_id: uuid.UUID, organization_id: uuid.UUID) -> ItemCategory | None:
        result = await self.db.execute(
            select(ItemCategory).where(
                ItemCategory.id == category_id, ItemCategory.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> ItemCategory | None:
        result = await self.db.execute(
            select(ItemCategory).where(
                ItemCategory.organization_id == organization_id, ItemCategory.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[ItemCategory]:
        conditions = [ItemCategory.organization_id == organization_id]
        if is_active is not None:
            conditions.append(ItemCategory.is_active == is_active)
        result = await self.db.execute(select(ItemCategory).where(*conditions).order_by(ItemCategory.name.asc()))
        return list(result.scalars().all())

    async def update(self, category: ItemCategory, **fields) -> ItemCategory:
        for key, value in fields.items():
            if value is not None:
                setattr(category, key, value)
        await self.db.flush()
        await self.db.refresh(category)
        return category


class WarehouseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Warehouse:
        warehouse = Warehouse(**fields)
        self.db.add(warehouse)
        await self.db.flush()
        await self.db.refresh(warehouse)
        return warehouse

    async def get_by_id(self, warehouse_id: uuid.UUID, organization_id: uuid.UUID) -> Warehouse | None:
        result = await self.db.execute(
            select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> Warehouse | None:
        result = await self.db.execute(
            select(Warehouse).where(Warehouse.organization_id == organization_id, Warehouse.code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[Warehouse]:
        conditions = [Warehouse.organization_id == organization_id]
        if is_active is not None:
            conditions.append(Warehouse.is_active == is_active)
        result = await self.db.execute(select(Warehouse).where(*conditions).order_by(Warehouse.name.asc()))
        return list(result.scalars().all())

    async def update(self, warehouse: Warehouse, **fields) -> Warehouse:
        for key, value in fields.items():
            if value is not None:
                setattr(warehouse, key, value)
        await self.db.flush()
        await self.db.refresh(warehouse)
        return warehouse


class InventoryItemRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> InventoryItem:
        item = InventoryItem(**fields)
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_by_id(self, item_id: uuid.UUID, organization_id: uuid.UUID) -> InventoryItem | None:
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.id == item_id, InventoryItem.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, organization_id: uuid.UUID, sku: str) -> InventoryItem | None:
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.organization_id == organization_id, InventoryItem.sku == sku
            )
        )
        return result.scalar_one_or_none()

    async def lock_for_update(self, item_id: uuid.UUID, organization_id: uuid.UUID) -> InventoryItem | None:
        """Same lookup as ``get_by_id`` but takes a ``SELECT ... FOR UPDATE`` row
        lock. On-hand stock is derived by summing transactions (there is no
        balance row to lock), so stock-reducing operations serialise on the
        owning item row to make the availability check-then-insert atomic and
        stop concurrent issues/adjustments/transfers overselling into negative
        stock."""
        result = await self.db.execute(
            select(InventoryItem)
            .where(InventoryItem.id == item_id, InventoryItem.organization_id == organization_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        category_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[InventoryItem], int]:
        conditions = [InventoryItem.organization_id == organization_id]
        if category_id is not None:
            conditions.append(InventoryItem.category_id == category_id)
        if is_active is not None:
            conditions.append(InventoryItem.is_active == is_active)
        if search:
            like_pattern = f"%{search}%"
            conditions.append((InventoryItem.name.ilike(like_pattern)) | (InventoryItem.sku.ilike(like_pattern)))

        count_result = await self.db.execute(select(func.count()).select_from(InventoryItem).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(InventoryItem).where(*conditions).order_by(InventoryItem.name.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_all_active(self, organization_id: uuid.UUID) -> list[InventoryItem]:
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.organization_id == organization_id, InventoryItem.is_active.is_(True)
            )
        )
        return list(result.scalars().all())

    async def update(self, item: InventoryItem, **fields) -> InventoryItem:
        for key, value in fields.items():
            if value is not None:
                setattr(item, key, value)
        await self.db.flush()
        await self.db.refresh(item)
        return item


class StockTransactionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> StockTransaction:
        transaction = StockTransaction(**fields)
        self.db.add(transaction)
        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def list_for_item(
        self,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[StockTransaction], int]:
        conditions = [StockTransaction.item_id == item_id]
        if warehouse_id is not None:
            conditions.append(StockTransaction.warehouse_id == warehouse_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(StockTransaction).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(StockTransaction)
            .where(*conditions)
            .order_by(StockTransaction.transaction_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def sum_by_type(
        self, item_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> list[tuple[str, float]]:
        conditions = [StockTransaction.item_id == item_id]
        if warehouse_id is not None:
            conditions.append(StockTransaction.warehouse_id == warehouse_id)
        result = await self.db.execute(
            select(StockTransaction.transaction_type, func.coalesce(func.sum(StockTransaction.quantity), 0))
            .where(*conditions)
            .group_by(StockTransaction.transaction_type)
        )
        return [(row[0], float(row[1])) for row in result.all()]

    async def on_hand_by_items(
        self, item_ids: list[uuid.UUID], warehouse_id: uuid.UUID | None = None
    ) -> dict[uuid.UUID, float]:
        """Quantity-on-hand for many items in a single grouped query.

        Groups by ``(item_id, transaction_type)`` and folds each item's rows the
        same way ``get_stock_level`` does (increasing types add, everything else
        subtracts), returning ``{item_id: on_hand}``. Lets callers that need the
        on-hand for a whole item set avoid the per-item `sum_by_type` N+1. Items
        with no transactions are simply absent (caller treats as 0)."""
        from modules.inventory.models import INCREASING_TRANSACTION_TYPES

        if not item_ids:
            return {}
        conditions = [StockTransaction.item_id.in_(item_ids)]
        if warehouse_id is not None:
            conditions.append(StockTransaction.warehouse_id == warehouse_id)
        result = await self.db.execute(
            select(
                StockTransaction.item_id,
                StockTransaction.transaction_type,
                func.coalesce(func.sum(StockTransaction.quantity), 0),
            )
            .where(*conditions)
            .group_by(StockTransaction.item_id, StockTransaction.transaction_type)
        )
        on_hand: dict[uuid.UUID, float] = {}
        for item_id, transaction_type, quantity in result.all():
            delta = float(quantity) if transaction_type in INCREASING_TRANSACTION_TYPES else -float(quantity)
            on_hand[item_id] = on_hand.get(item_id, 0.0) + delta
        return on_hand

    async def receiving_transactions(
        self, item_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> list[StockTransaction]:
        from modules.inventory.models import INCREASING_TRANSACTION_TYPES

        conditions = [
            StockTransaction.item_id == item_id,
            StockTransaction.transaction_type.in_(list(INCREASING_TRANSACTION_TYPES)),
        ]
        if warehouse_id is not None:
            conditions.append(StockTransaction.warehouse_id == warehouse_id)
        result = await self.db.execute(select(StockTransaction).where(*conditions))
        return list(result.scalars().all())
