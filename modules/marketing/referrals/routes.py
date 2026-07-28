import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.marketing.referrals.models import ReferralStatus
from modules.marketing.referrals.schemas import (
    MessageResponse,
    ReferralConvertRequest,
    ReferralCreateRequest,
    ReferralProgramCreateRequest,
    ReferralProgramPublic,
    ReferralProgramUpdateRequest,
    ReferralPublic,
)
from modules.marketing.referrals.service import ReferralProgramService, ReferralService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Referral Programs ----


@router.post("/programs", response_model=ReferralProgramPublic, status_code=status.HTTP_201_CREATED)
async def create_program(
    payload: ReferralProgramCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralProgramService(db)
    program = await service.create_program(organization_id, **payload.model_dump())
    return ReferralProgramPublic.model_validate(program)


@router.get("/programs", response_model=list[ReferralProgramPublic])
async def list_programs(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralProgramService(db)
    programs = await service.list_programs(organization_id, is_active)
    return [ReferralProgramPublic.model_validate(p) for p in programs]


@router.patch("/programs/{program_id}", response_model=ReferralProgramPublic)
async def update_program(
    program_id: uuid.UUID,
    payload: ReferralProgramUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralProgramService(db)
    program = await service.update_program(program_id, organization_id, **payload.model_dump(exclude_unset=True))
    return ReferralProgramPublic.model_validate(program)


# ---- Referrals ----


@router.post("", response_model=ReferralPublic, status_code=status.HTTP_201_CREATED)
async def create_referral(
    payload: ReferralCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralService(db)
    referral = await service.create_referral(organization_id, **payload.model_dump())
    return ReferralPublic.model_validate(referral)


@router.get("", response_model=dict)
async def list_referrals(
    referral_program_id: uuid.UUID | None = None,
    status_filter: ReferralStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralService(db)
    referrals, total = await service.list_referrals(
        organization_id, referral_program_id=referral_program_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [ReferralPublic.model_validate(r) for r in referrals],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/referrers/{referrer_student_id}", response_model=list[ReferralPublic])
async def list_for_referrer(
    referrer_student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralService(db)
    referrals = await service.list_for_referrer(referrer_student_id, organization_id)
    return [ReferralPublic.model_validate(r) for r in referrals]


@router.get("/{referral_id}", response_model=ReferralPublic)
async def get_referral(
    referral_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralService(db)
    referral = await service.get_referral(referral_id, organization_id)
    return ReferralPublic.model_validate(referral)


@router.post("/{referral_id}/convert", response_model=ReferralPublic)
async def convert_referral(
    referral_id: uuid.UUID,
    payload: ReferralConvertRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralService(db)
    referral = await service.mark_converted(referral_id, organization_id, payload.converted_lead_id)
    return ReferralPublic.model_validate(referral)


@router.post("/{referral_id}/reward", response_model=ReferralPublic)
async def reward_referral(
    referral_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralService(db)
    referral = await service.mark_rewarded(referral_id, organization_id)
    return ReferralPublic.model_validate(referral)


@router.post("/{referral_id}/reject", response_model=ReferralPublic)
async def reject_referral(
    referral_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.referrals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ReferralService(db)
    referral = await service.reject_referral(referral_id, organization_id)
    return ReferralPublic.model_validate(referral)
