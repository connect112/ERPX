"""
Ledger totals for one application, in Decimal. Confirmed money only counts as paid; a bank/UPI claim waiting for a
finance check counts as waiting, never as paid.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.internship_onboarding.fees import q, total_of
from modules.internship_onboarding.models import OnboardingApplication, PaymentOrder, PaymentTransaction

ZERO = Decimal("0.00")


@dataclass
class Totals:
    base: Decimal  # the accepted fee (or the current fee before acceptance)
    charges: Decimal
    waivers: Decimal
    paid: Decimal
    refunded: Decimal
    awaiting_manual: bool
    open_order: bool
    last_attempt_failed: bool

    @property
    def payable(self) -> Decimal:
        return q(max(ZERO, self.base + self.charges - self.waivers))

    @property
    def balance(self) -> Decimal:
        return q(max(ZERO, self.payable - (self.paid - self.refunded)))


async def totals(db: AsyncSession, application: OnboardingApplication, current_total: Decimal) -> Totals:
    rows = (
        await db.execute(
            select(PaymentTransaction.kind, PaymentTransaction.status, func.coalesce(func.sum(PaymentTransaction.amount), 0))
            .where(PaymentTransaction.application_id == application.id)
            .group_by(PaymentTransaction.kind, PaymentTransaction.status)
        )
    ).all()
    sums: dict[tuple[str, str], Decimal] = {(k, s): Decimal(v) for k, s, v in rows}

    def confirmed(kind: str) -> Decimal:
        return sums.get((kind, "confirmed"), ZERO)

    last = (
        await db.execute(
            select(PaymentTransaction.status)
            .where(PaymentTransaction.application_id == application.id, PaymentTransaction.kind == "payment")
            .order_by(PaymentTransaction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    open_order = (
        await db.execute(
            select(PaymentOrder.id).where(PaymentOrder.application_id == application.id, PaymentOrder.status.in_(("created", "active"))).limit(1)
        )
    ).first() is not None
    base = total_of(application.fee_snapshot) if application.fee_snapshot else current_total
    return Totals(
        base=base,
        charges=confirmed("charge"),
        waivers=confirmed("waiver"),
        paid=confirmed("payment"),
        refunded=confirmed("refund"),
        awaiting_manual=(("payment", "awaiting_verification") in sums),
        open_order=open_order,
        last_attempt_failed=last in ("failed", "rejected"),
    )


async def late_fee_charge(db: AsyncSession, application_id: uuid.UUID) -> PaymentTransaction | None:
    return (
        await db.execute(
            select(PaymentTransaction).where(
                PaymentTransaction.application_id == application_id,
                PaymentTransaction.kind == "charge",
                PaymentTransaction.note == "late_fee",
                PaymentTransaction.status == "confirmed",
            )
        )
    ).scalar_one_or_none()
