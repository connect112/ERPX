import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.marketing.coupons.schemas import (
    CouponCreateRequest,
    CouponPublic,
    CouponRedeemRequest,
    CouponRedemptionPublic,
    CouponUpdateRequest,
    CouponUsageSummaryResponse,
    CouponValidateRequest,
    CouponValidationResponse,
    MessageResponse,
)
from modules.marketing.coupons.service import CouponService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=CouponPublic, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    payload: CouponCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    coupon = await service.create_coupon(organization_id, **payload.model_dump())
    return CouponPublic.model_validate(coupon)


@router.get("", response_model=dict)
async def list_coupons(
    campaign_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    coupons, total = await service.list_coupons(
        organization_id, campaign_id=campaign_id, is_active=is_active, skip=skip, limit=limit
    )
    return {
        "items": [CouponPublic.model_validate(c) for c in coupons],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{coupon_id}", response_model=CouponPublic)
async def get_coupon(
    coupon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    coupon = await service.get_coupon(coupon_id, organization_id)
    return CouponPublic.model_validate(coupon)


@router.patch("/{coupon_id}", response_model=CouponPublic)
async def update_coupon(
    coupon_id: uuid.UUID,
    payload: CouponUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    coupon = await service.update_coupon(coupon_id, organization_id, **payload.model_dump(exclude_unset=True))
    return CouponPublic.model_validate(coupon)


@router.get("/{coupon_id}/usage-summary", response_model=CouponUsageSummaryResponse)
async def get_usage_summary(
    coupon_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    summary = await service.get_usage_summary(coupon_id, organization_id)
    return CouponUsageSummaryResponse(**summary)


@router.get("/{coupon_id}/redemptions", response_model=dict)
async def list_redemptions(
    coupon_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    redemptions, total = await service.list_redemptions(coupon_id, organization_id, skip=skip, limit=limit)
    return {
        "items": [CouponRedemptionPublic.model_validate(r) for r in redemptions],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/validate", response_model=CouponValidationResponse)
async def validate_coupon(
    payload: CouponValidateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.redeem")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    result = await service.validate_coupon(organization_id, **payload.model_dump())
    return CouponValidationResponse(**result)


@router.post("/redeem", response_model=CouponRedemptionPublic, status_code=status.HTTP_201_CREATED)
async def redeem_coupon(
    payload: CouponRedeemRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.coupons.redeem")),
    db: AsyncSession = Depends(get_db),
):
    service = CouponService(db)
    redemption = await service.redeem_coupon(organization_id, **payload.model_dump())
    return CouponRedemptionPublic.model_validate(redemption)
