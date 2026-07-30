"""
Regression tests for the inventory stock-level Decimal/float crash
(certification audit).

`StockService.get_stock_level` computed the moving-average cost as
`sum(t.quantity * float(t.unit_cost) ...)`. `t.quantity` is a SQLAlchemy
Numeric column → `decimal.Decimal`, and Python does not support
`Decimal * float`, so the method raised `TypeError` as soon as *any*
receiving transaction existed — a guaranteed 500 on the stock-level view and
on every reduction path that calls it (`issue_stock`, `adjust_stock`,
`transfer_stock`) and the low-stock report. This path had no prior test
coverage. The fix normalises the receipt quantity/cost to float.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ValidationError
from modules.inventory.models import StockTransactionType
from modules.inventory.repository import (
    InventoryItemRepository,
    StockTransactionRepository,
    WarehouseRepository,
)
from modules.inventory.service import StockService

pytestmark = pytest.mark.api


async def _seed_item(db_session, organization):
    item = await InventoryItemRepository(db_session).create(
        organization_id=organization.id, sku=f"SKU-{uuid.uuid4().hex[:8]}",
        name="Widget", unit_of_measure="unit", standard_cost=5,
    )
    warehouse = await WarehouseRepository(db_session).create(
        organization_id=organization.id, name="Main", code=f"WH-{uuid.uuid4().hex[:6]}",
    )
    await db_session.flush()
    return item, warehouse


async def _receive(db_session, organization, item, warehouse, quantity, unit_cost):
    await StockTransactionRepository(db_session).create(
        organization_id=organization.id, item_id=item.id, warehouse_id=warehouse.id,
        transaction_type=StockTransactionType.PURCHASE_RECEIPT,
        quantity=quantity, unit_cost=unit_cost, transaction_date=datetime.now(timezone.utc),
    )
    await db_session.flush()


async def test_get_stock_level_after_receipt_does_not_crash(db_session, organization):
    # Repro: on the pre-fix code this raised TypeError (Decimal * float).
    item, warehouse = await _seed_item(db_session, organization)
    await _receive(db_session, organization, item, warehouse, quantity=10, unit_cost=7)

    level = await StockService(db_session).get_stock_level(organization.id, item.id, warehouse.id)

    assert level["quantity_on_hand"] == pytest.approx(10.0)
    assert level["average_unit_cost"] == pytest.approx(7.0)
    assert isinstance(level["average_unit_cost"], float)


async def test_average_unit_cost_weights_multiple_receipts(db_session, organization):
    item, warehouse = await _seed_item(db_session, organization)
    await _receive(db_session, organization, item, warehouse, quantity=10, unit_cost=10)
    await _receive(db_session, organization, item, warehouse, quantity=30, unit_cost=20)

    level = await StockService(db_session).get_stock_level(organization.id, item.id, warehouse.id)

    # (10*10 + 30*20) / 40 = 17.5
    assert level["quantity_on_hand"] == pytest.approx(40.0)
    assert level["average_unit_cost"] == pytest.approx(17.5)


async def test_issue_stock_after_receipt_reduces_on_hand(db_session, organization):
    item, warehouse = await _seed_item(db_session, organization)
    await _receive(db_session, organization, item, warehouse, quantity=10, unit_cost=5)
    service = StockService(db_session)

    await service.issue_stock(organization.id, item.id, warehouse.id, quantity=6)
    level = await service.get_stock_level(organization.id, item.id, warehouse.id)
    assert level["quantity_on_hand"] == pytest.approx(4.0)

    # Availability guard still holds (only 4 left).
    with pytest.raises(ValidationError):
        await service.issue_stock(organization.id, item.id, warehouse.id, quantity=6)
