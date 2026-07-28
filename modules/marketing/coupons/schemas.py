import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.marketing.coupons.models import CouponDiscountType


class CouponCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=30)
    campaign_id: uuid.UUID | None = None
    description: str | None = None
    discount_type: CouponDiscountType
    discount_value: float = Field(..., gt=0)
    max_discount_amount: float | None = Field(default=None, ge=0)
    min_order_amount: float = Field(default=0, ge=0)
    usage_limit_total: int | None = Field(default=None, ge=1)
    usage_limit_per_customer: int = Field(default=1, ge=1)
    valid_from: date
    valid_until: date


class CouponUpdateRequest(BaseModel):
    description: str | None = None
    max_discount_amount: float | None = Field(default=None, ge=0)
    min_order_amount: float | None = Field(default=None, ge=0)
    usage_limit_total: int | None = Field(default=None, ge=1)
    usage_limit_per_customer: int | None = Field(default=None, ge=1)
    valid_until: date | None = None
    is_active: bool | None = None


class CouponPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    campaign_id: uuid.UUID | None
    code: str
    description: str | None
    discount_type: CouponDiscountType
    discount_value: float
    max_discount_amount: float | None
    min_order_amount: float
    usage_limit_total: int | None
    usage_limit_per_customer: int
    valid_from: date
    valid_until: date
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponValidateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=30)
    order_amount: float = Field(..., gt=0)
    customer_reference: str = Field(..., min_length=1)


class CouponValidationResponse(BaseModel):
    valid: bool
    coupon_id: uuid.UUID | None = None
    discount_amount: float = 0
    reason: str | None = None


class CouponRedeemRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=30)
    order_amount: float = Field(..., gt=0)
    customer_reference: str = Field(..., min_length=1)
    redeemed_against_type: str | None = None
    redeemed_against_id: uuid.UUID | None = None


class CouponRedemptionPublic(BaseModel):
    id: uuid.UUID
    coupon_id: uuid.UUID
    redeemed_by_reference: str
    redeemed_against_type: str | None
    redeemed_against_id: uuid.UUID | None
    order_amount: float
    discount_amount_applied: float
    redeemed_at: datetime

    model_config = {"from_attributes": True}


class CouponUsageSummaryResponse(BaseModel):
    coupon_id: uuid.UUID
    redemption_count: int
    total_discount_given: float


class MessageResponse(BaseModel):
    message: str
