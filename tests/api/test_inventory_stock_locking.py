"""
Regression tests for the inventory stock-oversell TOCTOU.

On-hand stock is derived live by summing transactions, and the stock-reducing
operations (`issue_stock`, `adjust_stock` reduce-branch, `transfer_stock`) did a
check-then-insert against that derived on-hand with no locking: two concurrent
reductions of the same item can both read the same on-hand and both succeed,
overselling into negative stock. The fix serialises reductions of an item by
taking a `SELECT ... FOR UPDATE` row lock on the owning `InventoryItem`
(`InventoryItemRepository.lock_for_update`) before the availability check.

A wall-clock race is not deterministically reproducible in one event loop, so
these pin the mechanism deterministically: each reducing path must emit a
`FOR UPDATE` on `inventory_items` (removing the lock fails these), plus a
sequential guard that availability is still enforced.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from app.core.exceptions import ValidationError
from modules.inventory.models import StockTransactionType
from modules.inventory.repository import (
    InventoryItemRepository,
    StockTransactionRepository,
    WarehouseRepository,
)
from modules.inventory.service import StockService

pytestmark = pytest.mark.api


async def _seed(db_session, organization, on_hand=20.0):
    item = await InventoryItemRepository(db_session).create(
        organization_id=organization.id, sku=f"SKU-{uuid.uuid4().hex[:8]}",
        name="Widget", unit_of_measure="unit", standard_cost=5,
    )
    wh = await WarehouseRepository(db_session).create(
        organization_id=organization.id, name="Main", code=f"WH-{uuid.uuid4().hex[:6]}",
    )
    wh2 = await WarehouseRepository(db_session).create(
        organization_id=organization.id, name="Alt", code=f"WH-{uuid.uuid4().hex[:6]}",
    )
    await StockTransactionRepository(db_session).create(
        organization_id=organization.id, item_id=item.id, warehouse_id=wh.id,
        transaction_type=StockTransactionType.PURCHASE_RECEIPT, quantity=on_hand,
        unit_cost=5, transaction_date=datetime.now(timezone.utc),
    )
    await db_session.flush()
    return item, wh, wh2


class _LockCapture:
    def __init__(self):
        from app.db.session import engine

        self._engine = engine.sync_engine
        self.statements: list[str] = []

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._on)

    def _on(self, conn, cursor, statement, params, context, executemany):
        self.statements.append(statement.lower())

    @property
    def locked_item(self) -> bool:
        return any("inventory_items" in s and "for update" in s for s in self.statements)


async def test_issue_stock_locks_the_item_row(db_session, organization):
    item, wh, _ = await _seed(db_session, organization)
    with _LockCapture() as cap:
        await StockService(db_session).issue_stock(organization.id, item.id, wh.id, quantity=3)
    assert cap.locked_item, "issue_stock must SELECT ... FOR UPDATE the item row"


async def test_adjust_stock_reduction_locks_the_item_row(db_session, organization):
    item, wh, _ = await _seed(db_session, organization)
    with _LockCapture() as cap:
        await StockService(db_session).adjust_stock(
            organization.id, item.id, wh.id, quantity_change=-3, reason="shrinkage"
        )
    assert cap.locked_item, "adjust_stock (reduction) must SELECT ... FOR UPDATE the item row"


async def test_transfer_stock_locks_the_item_row(db_session, organization):
    item, wh, wh2 = await _seed(db_session, organization)
    with _LockCapture() as cap:
        await StockService(db_session).transfer_stock(organization.id, item.id, wh.id, wh2.id, quantity=3)
    assert cap.locked_item, "transfer_stock must SELECT ... FOR UPDATE the item row"


async def test_availability_guard_still_enforced(db_session, organization):
    item, wh, _ = await _seed(db_session, organization, on_hand=10)
    service = StockService(db_session)
    await service.issue_stock(organization.id, item.id, wh.id, quantity=6)
    with pytest.raises(ValidationError):
        await service.issue_stock(organization.id, item.id, wh.id, quantity=6)
    level = await service.get_stock_level(organization.id, item.id, wh.id)
    assert level["quantity_on_hand"] == pytest.approx(4.0)
