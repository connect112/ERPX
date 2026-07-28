"""
Unit tests for pure calculation logic that doesn't need a database —
coupon discount computation, straight-line/declining-balance
depreciation, and scheduled-report recurrence math.
"""

from datetime import datetime, timezone

import pytest

from modules.assets.models import DepreciationMethod
from modules.assets.service import _monthly_depreciation
from modules.marketing.coupons.models import Coupon, CouponDiscountType
from modules.marketing.coupons.service import _compute_discount
from modules.reports.models import ScheduleFrequency
from modules.reports.service import _next_occurrence

pytestmark = pytest.mark.unit


# ---- Coupons ----


def _coupon(**overrides) -> Coupon:
    defaults = dict(
        discount_type=CouponDiscountType.PERCENTAGE,
        discount_value=10,
        max_discount_amount=None,
    )
    defaults.update(overrides)
    return Coupon(**defaults)


def test_percentage_discount_computed_correctly():
    coupon = _coupon(discount_type=CouponDiscountType.PERCENTAGE, discount_value=20)
    assert _compute_discount(coupon, 1000) == 200.0


def test_percentage_discount_capped_by_max_discount_amount():
    coupon = _coupon(discount_type=CouponDiscountType.PERCENTAGE, discount_value=50, max_discount_amount=100)
    assert _compute_discount(coupon, 1000) == 100.0


def test_fixed_amount_discount_returned_as_is():
    coupon = _coupon(discount_type=CouponDiscountType.FIXED_AMOUNT, discount_value=75)
    assert _compute_discount(coupon, 1000) == 75.0


def test_discount_never_exceeds_order_amount():
    coupon = _coupon(discount_type=CouponDiscountType.FIXED_AMOUNT, discount_value=500)
    assert _compute_discount(coupon, 100) == 100.0


# ---- Asset Depreciation ----


def test_straight_line_monthly_depreciation():
    # (12000 - 0) / 5 years / 12 months = 200/month
    monthly = _monthly_depreciation(DepreciationMethod.STRAIGHT_LINE, 12000, 0, 5, accumulated_so_far=0)
    assert monthly == 200.0


def test_straight_line_depreciation_caps_at_depreciable_base():
    monthly = _monthly_depreciation(DepreciationMethod.STRAIGHT_LINE, 12000, 0, 5, accumulated_so_far=11900)
    assert monthly == 100.0  # only 100 left before hitting the depreciable base


def test_straight_line_fully_depreciated_returns_zero():
    monthly = _monthly_depreciation(DepreciationMethod.STRAIGHT_LINE, 12000, 0, 5, accumulated_so_far=12000)
    assert monthly == 0.0


def test_declining_balance_depreciation_shrinks_over_time():
    first_month = _monthly_depreciation(DepreciationMethod.DECLINING_BALANCE, 10000, 0, 5, accumulated_so_far=0)
    later_month = _monthly_depreciation(DepreciationMethod.DECLINING_BALANCE, 10000, 0, 5, accumulated_so_far=5000)
    assert first_month > later_month > 0


def test_depreciation_respects_salvage_value():
    monthly = _monthly_depreciation(DepreciationMethod.STRAIGHT_LINE, 10000, 1000, 3, accumulated_so_far=8990)
    assert monthly == 10.0  # only 10 left before hitting the 9000 depreciable base


# ---- Scheduled Report Recurrence ----


def test_next_occurrence_daily():
    current = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    result = _next_occurrence(current, ScheduleFrequency.DAILY)
    assert result == datetime(2026, 1, 16, 10, 0, tzinfo=timezone.utc)


def test_next_occurrence_weekly():
    current = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    result = _next_occurrence(current, ScheduleFrequency.WEEKLY)
    assert result == datetime(2026, 1, 22, 10, 0, tzinfo=timezone.utc)


def test_next_occurrence_monthly_rolls_over_year():
    current = datetime(2026, 12, 15, 10, 0, tzinfo=timezone.utc)
    result = _next_occurrence(current, ScheduleFrequency.MONTHLY)
    assert result == datetime(2027, 1, 15, 10, 0, tzinfo=timezone.utc)


def test_next_occurrence_monthly_clamps_day_for_short_month():
    # Jan 31 -> Feb has no 31st, should clamp to Feb 28 (2026 is not a leap year)
    current = datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)
    result = _next_occurrence(current, ScheduleFrequency.MONTHLY)
    assert result == datetime(2026, 2, 28, 10, 0, tzinfo=timezone.utc)
