import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.marketing.coupons.models import Coupon, CouponRedemption


class CouponRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Coupon:
        coupon = Coupon(**fields)
        self.db.add(coupon)
        await self.db.flush()
        await self.db.refresh(coupon)
        return coupon

    async def get_by_id(self, coupon_id: uuid.UUID, organization_id: uuid.UUID) -> Coupon | None:
        result = await self.db.execute(
            select(Coupon).where(Coupon.id == coupon_id, Coupon.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> Coupon | None:
        result = await self.db.execute(
            select(Coupon).where(Coupon.organization_id == organization_id, Coupon.code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_code_for_update(self, organization_id: uuid.UUID, code: str) -> Coupon | None:
        """Same lookup as ``get_by_code`` but takes a ``SELECT ... FOR UPDATE``
        row lock, so concurrent redemptions of the same coupon serialize and the
        usage-limit check-then-insert becomes atomic (prevents over-redemption)."""
        result = await self.db.execute(
            select(Coupon)
            .where(Coupon.organization_id == organization_id, Coupon.code == code)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Coupon], int]:
        conditions = [Coupon.organization_id == organization_id]
        if campaign_id is not None:
            conditions.append(Coupon.campaign_id == campaign_id)
        if is_active is not None:
            conditions.append(Coupon.is_active == is_active)

        count_result = await self.db.execute(select(func.count()).select_from(Coupon).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Coupon).where(*conditions).order_by(Coupon.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, coupon: Coupon, **fields) -> Coupon:
        for key, value in fields.items():
            if value is not None:
                setattr(coupon, key, value)
        await self.db.flush()
        await self.db.refresh(coupon)
        return coupon


class CouponRedemptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> CouponRedemption:
        redemption = CouponRedemption(**fields)
        self.db.add(redemption)
        await self.db.flush()
        await self.db.refresh(redemption)
        return redemption

    async def count_for_coupon(self, coupon_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(CouponRedemption).where(CouponRedemption.coupon_id == coupon_id)
        )
        return result.scalar_one()

    async def count_for_coupon_and_customer(self, coupon_id: uuid.UUID, redeemed_by_reference: str) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(CouponRedemption)
            .where(
                CouponRedemption.coupon_id == coupon_id,
                CouponRedemption.redeemed_by_reference == redeemed_by_reference,
            )
        )
        return result.scalar_one()

    async def list_for_coupon(self, coupon_id: uuid.UUID, skip: int = 0, limit: int = 50) -> tuple[list[CouponRedemption], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(CouponRedemption).where(CouponRedemption.coupon_id == coupon_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(CouponRedemption)
            .where(CouponRedemption.coupon_id == coupon_id)
            .order_by(CouponRedemption.redeemed_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def sum_discount_for_coupon(self, coupon_id: uuid.UUID) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(CouponRedemption.discount_amount_applied), 0)).where(
                CouponRedemption.coupon_id == coupon_id
            )
        )
        return float(result.scalar_one())

    async def totals_for_coupons(self, coupon_ids: list[uuid.UUID]) -> tuple[int, float]:
        """Redemption count + total discount across many coupons in one query.

        Aggregates the same values ``count_for_coupon``/``sum_discount_for_coupon``
        return per coupon, but for a whole set at once — the sum of per-coupon
        counts is exactly ``COUNT(*)`` over all those coupons' redemptions, and
        the sum of per-coupon discount sums is exactly ``SUM(discount)`` over
        them — replacing an N+1 (two queries per coupon) with a single scan.
        """
        if not coupon_ids:
            return 0, 0.0
        result = await self.db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(CouponRedemption.discount_amount_applied), 0),
            ).where(CouponRedemption.coupon_id.in_(coupon_ids))
        )
        row = result.one()
        return int(row[0]), float(row[1])
