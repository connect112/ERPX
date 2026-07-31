"""
Regression tests for the low-stock report N+1.

`StockService.list_low_stock_items` called `get_stock_level` per active item —
3 queries each (a redundant item lookup + sum_by_type + an unused average-cost
query), i.e. 1 + 3N queries. The report only needs quantity_on_hand, so this is
replaced by one grouped `on_hand_by_items` query (StockTransactionRepository),
giving a constant 2 queries regardless of item count.

Tests assert the flagged items and their on-hand are unchanged and pin the
query count — which fails on the pre-fix per-item code and passes after.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from modules.inventory.models import StockTransactionType
from modules.inventory.repository import (
    InventoryItemRepository,
    StockTransactionRepository,
    WarehouseRepository,
)
from modules.inventory.service import StockService

pytestmark = pytest.mark.api


class _StatementCounter:
    def __init__(self):
        from app.db.session import engine

        self._engine = engine.sync_engine
        self.count = 0

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._on)

    def _on(self, conn, cursor, statement, params, context, executemany):
        self.count += 1


async def _item(db_session, organization, reorder_level):
    return await InventoryItemRepository(db_session).create(
        organization_id=organization.id, sku=f"SKU-{uuid.uuid4().hex[:8]}",
        name="Item", unit_of_measure="unit", reorder_level=reorder_level,
    )


async def _txn(db_session, organization, item, warehouse, ttype, qty):
    await StockTransactionRepository(db_session).create(
        organization_id=organization.id, item_id=item.id, warehouse_id=warehouse.id,
        transaction_type=ttype, quantity=qty, unit_cost=2,
        transaction_date=datetime.now(timezone.utc),
    )


async def test_low_stock_report_is_correct_and_uses_constant_queries(db_session, organization):
    wh = await WarehouseRepository(db_session).create(
        organization_id=organization.id, name="Main", code=f"WH-{uuid.uuid4().hex[:6]}"
    )
    below = await _item(db_session, organization, reorder_level=5)      # on-hand 3 -> low
    above = await _item(db_session, organization, reorder_level=5)      # on-hand 10 -> not low
    net = await _item(db_session, organization, reorder_level=5)        # 10 - 8 = 2 -> low
    empty = await _item(db_session, organization, reorder_level=5)      # no txns -> 0 -> low

    await _txn(db_session, organization, below, wh, StockTransactionType.PURCHASE_RECEIPT, 3)
    await _txn(db_session, organization, above, wh, StockTransactionType.PURCHASE_RECEIPT, 10)
    await _txn(db_session, organization, net, wh, StockTransactionType.PURCHASE_RECEIPT, 10)
    await _txn(db_session, organization, net, wh, StockTransactionType.SALE_ISSUE, 8)
    await db_session.flush()

    with _StatementCounter() as counter:
        result = await StockService(db_session).list_low_stock_items(organization.id)

    by_id = {r["item_id"]: r for r in result}
    assert set(by_id) == {below.id, net.id, empty.id}      # `above` excluded
    assert by_id[below.id]["quantity_on_hand"] == pytest.approx(3.0)
    assert by_id[net.id]["quantity_on_hand"] == pytest.approx(2.0)
    assert by_id[empty.id]["quantity_on_hand"] == pytest.approx(0.0)

    # One list query + one grouped on-hand query — not 1 + 3N.
    assert counter.count == 2


async def test_low_stock_report_empty_org_no_queries_explode(db_session, organization):
    with _StatementCounter() as counter:
        result = await StockService(db_session).list_low_stock_items(organization.id)

    assert result == []
    # Only the active-items list runs; on_hand_by_items short-circuits on []
    assert counter.count == 1
