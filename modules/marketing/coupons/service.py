import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.marketing.campaigns.repository import CampaignRepository
from modules.marketing.coupons.models import Coupon, CouponDiscountType, CouponRedemption
from modules.marketing.coupons.repository import CouponRedemptionRepository, CouponRepository

logger = get_logger(__name__)


def _compute_discount(coupon: Coupon, order_amount: float) -> float:
    if coupon.discount_type == CouponDiscountType.PERCENTAGE:
        discount = order_amount * float(coupon.discount_value) / 100
        if coupon.max_discount_amount is not None:
            discount = min(discount, float(coupon.max_discount_amount))
    else:
        discount = float(coupon.discount_value)
    return round(min(discount, order_amount), 2)


class CouponService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CouponRepository(db)
        self.campaign_repo = CampaignRepository(db)
        self.redemption_repo = CouponRedemptionRepository(db)

    async def create_coupon(
        self, organization_id: uuid.UUID, code: str, campaign_id: uuid.UUID | None = None, **fields
    ) -> Coupon:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A coupon with code '{code}' already exists.")
        if campaign_id is not None:
            campaign = await self.campaign_repo.get_by_id(campaign_id, organization_id)
            if not campaign:
                raise NotFoundError("Campaign", campaign_id)
        if fields["valid_until"] < fields["valid_from"]:
            raise ValidationError("valid_until cannot be before valid_from.")

        coupon = await self.repo.create(organization_id=organization_id, code=code, campaign_id=campaign_id, **fields)
        logger.info("coupon_created", coupon_id=str(coupon.id), code=code)
        return coupon

    async def get_coupon(self, coupon_id: uuid.UUID, organization_id: uuid.UUID) -> Coupon:
        coupon = await self.repo.get_by_id(coupon_id, organization_id)
        if not coupon:
            raise NotFoundError("Coupon", coupon_id)
        return coupon

    async def list_coupons(self, organization_id: uuid.UUID, **filters) -> tuple[list[Coupon], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_coupon(self, coupon_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Coupon:
        coupon = await self.get_coupon(coupon_id, organization_id)
        updated = await self.repo.update(coupon, **fields)
        logger.info("coupon_updated", coupon_id=str(coupon_id))
        return updated

    async def _validate(
        self, organization_id: uuid.UUID, code: str, order_amount: float, customer_reference: str
    ) -> tuple[Coupon | None, float, str | None]:
        coupon = await self.repo.get_by_code(organization_id, code)
        if not coupon:
            return None, 0, "Coupon code not found."
        if not coupon.is_active:
            return None, 0, "This coupon is not active."

        today = date.today()
        if today < coupon.valid_from or today > coupon.valid_until:
            return None, 0, "This coupon is outside its valid date range."
        if order_amount < float(coupon.min_order_amount):
            return None, 0, f"Order amount must be at least {coupon.min_order_amount} to use this coupon."

        if coupon.usage_limit_total is not None:
            total_used = await self.redemption_repo.count_for_coupon(coupon.id)
            if total_used >= coupon.usage_limit_total:
                return None, 0, "This coupon has reached its total usage limit."

        customer_used = await self.redemption_repo.count_for_coupon_and_customer(coupon.id, customer_reference)
        if customer_used >= coupon.usage_limit_per_customer:
            return None, 0, "You have already used this coupon the maximum number of times."

        discount = _compute_discount(coupon, order_amount)
        return coupon, discount, None

    async def validate_coupon(
        self, organization_id: uuid.UUID, code: str, order_amount: float, customer_reference: str
    ) -> dict:
        coupon, discount, reason = await self._validate(organization_id, code, order_amount, customer_reference)
        return {
            "valid": coupon is not None,
            "coupon_id": coupon.id if coupon else None,
            "discount_amount": discount,
            "reason": reason,
        }

    async def redeem_coupon(
        self,
        organization_id: uuid.UUID,
        code: str,
        order_amount: float,
        customer_reference: str,
        redeemed_against_type: str | None = None,
        redeemed_against_id: uuid.UUID | None = None,
    ) -> CouponRedemption:
        # Lock the coupon row for the rest of this transaction so that
        # concurrent redemptions of the same code serialize: the second waiter
        # only proceeds after the first commits, and its usage-limit count then
        # sees the first redemption — closing the check-then-insert TOCTOU that
        # otherwise lets a limited coupon be redeemed past its cap.
        await self.repo.get_by_code_for_update(organization_id, code)
        coupon, discount, reason = await self._validate(organization_id, code, order_amount, customer_reference)
        if coupon is None:
            raise ValidationError(reason or "This coupon cannot be redeemed.")

        redemption = await self.redemption_repo.create(
            coupon_id=coupon.id,
            redeemed_by_reference=customer_reference,
            redeemed_against_type=redeemed_against_type,
            redeemed_against_id=redeemed_against_id,
            order_amount=order_amount,
            discount_amount_applied=discount,
            redeemed_at=datetime.now(timezone.utc),
        )
        logger.info("coupon_redeemed", coupon_id=str(coupon.id), discount=discount)
        return redemption

    async def get_usage_summary(self, coupon_id: uuid.UUID, organization_id: uuid.UUID) -> dict:
        await self.get_coupon(coupon_id, organization_id)
        redemption_count = await self.redemption_repo.count_for_coupon(coupon_id)
        total_discount = await self.redemption_repo.sum_discount_for_coupon(coupon_id)
        return {
            "coupon_id": coupon_id,
            "redemption_count": redemption_count,
            "total_discount_given": round(total_discount, 2),
        }

    async def list_redemptions(self, coupon_id: uuid.UUID, organization_id: uuid.UUID, **filters):
        await self.get_coupon(coupon_id, organization_id)
        return await self.redemption_repo.list_for_coupon(coupon_id, **filters)
