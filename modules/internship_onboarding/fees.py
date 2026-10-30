"""
What a student owes, in Decimal, rounded half-up to paise. Pure.

The snapshot taken when a student accepts the offer is what they agreed to; later configuration changes never alter it.
A late fee, when an administrator reopens onboarding late with a fee, is a separate charge added to the obligation, never
a recalculation of the accepted snapshot.
"""

from decimal import ROUND_HALF_UP, Decimal

from modules.internship_onboarding.config import Fees, LateFee

CENT = Decimal("0.01")


def q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def snapshot(fees: Fees) -> dict[str, str]:
    """The breakdown shown before acceptance and stored with it. All amounts are strings with two decimals."""
    base = q(fees.base_amount)
    discount = q(fees.discount_amount)
    net = base - discount
    rate = fees.tax_rate_percent
    if fees.tax_mode == "exclusive":
        tax = q(net * rate / 100)
        taxable, total = net, net + tax
    elif fees.tax_mode == "inclusive":
        taxable = q(net * 100 / (100 + rate))
        tax, total = net - taxable, net
    else:
        taxable, tax, total = net, Decimal("0.00"), net
    return {
        "currency": fees.currency,
        "description": fees.description,
        "base": str(base),
        "discount": str(discount),
        "taxable": str(q(taxable)),
        "tax_mode": fees.tax_mode,
        "tax_label": fees.tax_label,
        "tax_rate_percent": str(rate),
        "tax": str(q(tax)),
        "total": str(q(total)),
    }


def late_fee_amount(late: LateFee, total: Decimal) -> Decimal:
    if late.mode == "fixed":
        return q(late.value)
    if late.mode == "percent":
        return q(total * late.value / 100)
    return Decimal("0.00")


def total_of(snap: dict | None) -> Decimal:
    return Decimal(snap["total"]) if snap else Decimal("0.00")
