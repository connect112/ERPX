import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.inventory.models import (
    INCREASING_TRANSACTION_TYPES,
    InventoryItem,
    ItemCategory,
    StockTransaction,
    StockTransactionType,
    Warehouse,
)
from modules.inventory.repository import (
    InventoryItemRepository,
    ItemCategoryRepository,
    StockTransactionRepository,
    WarehouseRepository,
)

logger = get_logger(__name__)


class ItemCategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ItemCategoryRepository(db)

    async def create_category(self, organization_id: uuid.UUID, code: str, **fields) -> ItemCategory:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"An item category with code '{code}' already exists.")
        category = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("item_category_created", category_id=str(category.id))
        return category

    async def get_category(self, category_id: uuid.UUID, organization_id: uuid.UUID) -> ItemCategory:
        category = await self.repo.get_by_id(category_id, organization_id)
        if not category:
            raise NotFoundError("Item category", category_id)
        return category

    async def list_categories(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[ItemCategory]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_category(self, category_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> ItemCategory:
        category = await self.get_category(category_id, organization_id)
        updated = await self.repo.update(category, **fields)
        logger.info("item_category_updated", category_id=str(category_id))
        return updated


class WarehouseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WarehouseRepository(db)

    async def create_warehouse(self, organization_id: uuid.UUID, code: str, **fields) -> Warehouse:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A warehouse with code '{code}' already exists.")
        warehouse = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("warehouse_created", warehouse_id=str(warehouse.id))
        return warehouse

    async def get_warehouse(self, warehouse_id: uuid.UUID, organization_id: uuid.UUID) -> Warehouse:
        warehouse = await self.repo.get_by_id(warehouse_id, organization_id)
        if not warehouse:
            raise NotFoundError("Warehouse", warehouse_id)
        return warehouse

    async def list_warehouses(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[Warehouse]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_warehouse(self, warehouse_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Warehouse:
        warehouse = await self.get_warehouse(warehouse_id, organization_id)
        updated = await self.repo.update(warehouse, **fields)
        logger.info("warehouse_updated", warehouse_id=str(warehouse_id))
        return updated


class InventoryItemService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InventoryItemRepository(db)
        self.category_repo = ItemCategoryRepository(db)

    async def create_item(self, organization_id: uuid.UUID, sku: str, category_id: uuid.UUID | None, **fields) -> InventoryItem:
        existing = await self.repo.get_by_sku(organization_id, sku)
        if existing:
            raise ConflictError(f"An item with SKU '{sku}' already exists.")
        if category_id is not None:
            category = await self.category_repo.get_by_id(category_id, organization_id)
            if not category:
                raise NotFoundError("Item category", category_id)
        item = await self.repo.create(organization_id=organization_id, sku=sku, category_id=category_id, **fields)
        logger.info("inventory_item_created", item_id=str(item.id), sku=sku)
        return item

    async def get_item(self, item_id: uuid.UUID, organization_id: uuid.UUID) -> InventoryItem:
        item = await self.repo.get_by_id(item_id, organization_id)
        if not item:
            raise NotFoundError("Inventory item", item_id)
        return item

    async def list_items(self, organization_id: uuid.UUID, **filters) -> tuple[list[InventoryItem], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_item(self, item_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> InventoryItem:
        item = await self.get_item(item_id, organization_id)
        if fields.get("category_id") is not None:
            category = await self.category_repo.get_by_id(fields["category_id"], organization_id)
            if not category:
                raise NotFoundError("Item category", fields["category_id"])
        updated = await self.repo.update(item, **fields)
        logger.info("inventory_item_updated", item_id=str(item_id))
        return updated


class StockService:
    """
    Valuation uses a single blended weighted-average unit cost across an
    item's entire receiving history (`receiving_transactions`), not a
    perpetual moving average recomputed layer-by-layer at each issue —
    a deliberate simplification, the same kind Payroll documents for LOP
    deductions, adequate for a first-cut valuation without a full FIFO
    costing engine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = StockTransactionRepository(db)
        self.item_repo = InventoryItemRepository(db)
        self.warehouse_repo = WarehouseRepository(db)

    async def _get_item_and_warehouse(
        self, organization_id: uuid.UUID, item_id: uuid.UUID, warehouse_id: uuid.UUID
    ) -> tuple[InventoryItem, Warehouse]:
        item = await self.item_repo.get_by_id(item_id, organization_id)
        if not item:
            raise NotFoundError("Inventory item", item_id)
        warehouse = await self.warehouse_repo.get_by_id(warehouse_id, organization_id)
        if not warehouse:
            raise NotFoundError("Warehouse", warehouse_id)
        return item, warehouse

    async def get_stock_level(
        self, organization_id: uuid.UUID, item_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> dict:
        item = await self.item_repo.get_by_id(item_id, organization_id)
        if not item:
            raise NotFoundError("Inventory item", item_id)

        totals = await self.repo.sum_by_type(item_id, warehouse_id)
        quantity_on_hand = 0.0
        for transaction_type, quantity in totals:
            if transaction_type in INCREASING_TRANSACTION_TYPES:
                quantity_on_hand += quantity
            else:
                quantity_on_hand -= quantity

        receipts = await self.repo.receiving_transactions(item_id, warehouse_id)
        total_received_qty = sum(t.quantity for t in receipts)
        average_unit_cost = (
            sum(t.quantity * float(t.unit_cost) for t in receipts) / total_received_qty
            if total_received_qty > 0
            else float(item.standard_cost)
        )

        return {
            "item_id": item_id,
            "warehouse_id": warehouse_id,
            "quantity_on_hand": round(quantity_on_hand, 2),
            "average_unit_cost": round(average_unit_cost, 2),
            "stock_value": round(quantity_on_hand * average_unit_cost, 2),
        }

    async def receive_stock(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity: float,
        unit_cost: float,
        transaction_date: datetime | None = None,
        created_by_user_id: uuid.UUID | None = None,
        **fields,
    ) -> StockTransaction:
        await self._get_item_and_warehouse(organization_id, item_id, warehouse_id)
        transaction = await self.repo.create(
            organization_id=organization_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            transaction_type=StockTransactionType.PURCHASE_RECEIPT,
            quantity=quantity,
            unit_cost=unit_cost,
            transaction_date=transaction_date or datetime.now(timezone.utc),
            created_by_user_id=created_by_user_id,
            **fields,
        )
        logger.info("stock_received", item_id=str(item_id), warehouse_id=str(warehouse_id), quantity=quantity)
        return transaction

    async def issue_stock(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity: float,
        transaction_date: datetime | None = None,
        created_by_user_id: uuid.UUID | None = None,
        **fields,
    ) -> StockTransaction:
        await self._get_item_and_warehouse(organization_id, item_id, warehouse_id)
        level = await self.get_stock_level(organization_id, item_id, warehouse_id)
        if quantity > level["quantity_on_hand"] + 0.001:
            raise ValidationError(
                f"Cannot issue {quantity}: only {level['quantity_on_hand']} unit(s) available at this warehouse."
            )

        transaction = await self.repo.create(
            organization_id=organization_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            transaction_type=StockTransactionType.SALE_ISSUE,
            quantity=quantity,
            unit_cost=level["average_unit_cost"],
            transaction_date=transaction_date or datetime.now(timezone.utc),
            created_by_user_id=created_by_user_id,
            **fields,
        )
        logger.info("stock_issued", item_id=str(item_id), warehouse_id=str(warehouse_id), quantity=quantity)
        return transaction

    async def adjust_stock(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity_change: float,
        reason: str,
        unit_cost: float = 0,
        created_by_user_id: uuid.UUID | None = None,
    ) -> StockTransaction:
        await self._get_item_and_warehouse(organization_id, item_id, warehouse_id)
        if quantity_change == 0:
            raise ValidationError("quantity_change cannot be zero.")

        if quantity_change > 0:
            transaction_type = StockTransactionType.ADJUSTMENT_IN
            cost = unit_cost
        else:
            level = await self.get_stock_level(organization_id, item_id, warehouse_id)
            if abs(quantity_change) > level["quantity_on_hand"] + 0.001:
                raise ValidationError(
                    f"Cannot reduce stock by {abs(quantity_change)}: only "
                    f"{level['quantity_on_hand']} unit(s) available at this warehouse."
                )
            transaction_type = StockTransactionType.ADJUSTMENT_OUT
            cost = level["average_unit_cost"]

        transaction = await self.repo.create(
            organization_id=organization_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            transaction_type=transaction_type,
            quantity=abs(quantity_change),
            unit_cost=cost,
            transaction_date=datetime.now(timezone.utc),
            notes=reason,
            created_by_user_id=created_by_user_id,
        )
        logger.info("stock_adjusted", item_id=str(item_id), quantity_change=quantity_change, reason=reason)
        return transaction

    async def transfer_stock(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        from_warehouse_id: uuid.UUID,
        to_warehouse_id: uuid.UUID,
        quantity: float,
        notes: str | None = None,
        created_by_user_id: uuid.UUID | None = None,
    ) -> tuple[StockTransaction, StockTransaction]:
        if from_warehouse_id == to_warehouse_id:
            raise ValidationError("Source and destination warehouses must be different.")

        await self._get_item_and_warehouse(organization_id, item_id, from_warehouse_id)
        await self._get_item_and_warehouse(organization_id, item_id, to_warehouse_id)

        level = await self.get_stock_level(organization_id, item_id, from_warehouse_id)
        if quantity > level["quantity_on_hand"] + 0.001:
            raise ValidationError(
                f"Cannot transfer {quantity}: only {level['quantity_on_hand']} unit(s) available at the source warehouse."
            )

        now = datetime.now(timezone.utc)
        out_transaction = await self.repo.create(
            organization_id=organization_id,
            item_id=item_id,
            warehouse_id=from_warehouse_id,
            transaction_type=StockTransactionType.TRANSFER_OUT,
            quantity=quantity,
            unit_cost=level["average_unit_cost"],
            transaction_date=now,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )
        in_transaction = await self.repo.create(
            organization_id=organization_id,
            item_id=item_id,
            warehouse_id=to_warehouse_id,
            transaction_type=StockTransactionType.TRANSFER_IN,
            quantity=quantity,
            unit_cost=level["average_unit_cost"],
            transaction_date=now,
            notes=notes,
            created_by_user_id=created_by_user_id,
        )
        logger.info(
            "stock_transferred",
            item_id=str(item_id),
            from_warehouse_id=str(from_warehouse_id),
            to_warehouse_id=str(to_warehouse_id),
            quantity=quantity,
        )
        return out_transaction, in_transaction

    async def list_transactions(self, item_id: uuid.UUID, **filters):
        return await self.repo.list_for_item(item_id, **filters)

    async def list_low_stock_items(
        self, organization_id: uuid.UUID, warehouse_id: uuid.UUID | None = None
    ) -> list[dict]:
        items = await self.item_repo.list_all_active(organization_id)
        low_stock = []
        for item in items:
            level = await self.get_stock_level(organization_id, item.id, warehouse_id)
            if level["quantity_on_hand"] <= float(item.reorder_level):
                low_stock.append(
                    {
                        "item_id": item.id,
                        "sku": item.sku,
                        "name": item.name,
                        "reorder_level": float(item.reorder_level),
                        "quantity_on_hand": level["quantity_on_hand"],
                    }
                )
        return low_stock
