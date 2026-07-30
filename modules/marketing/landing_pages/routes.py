import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.marketing.landing_pages.models import LandingPageStatus
from modules.marketing.landing_pages.schemas import (
    LandingPageCreateRequest,
    LandingPagePublic,
    LandingPageStatsResponse,
    LandingPageUpdateRequest,
    LandingPageViewCreateRequest,
    LandingPageViewPublic,
    MessageResponse,
)
from modules.marketing.landing_pages.service import LandingPageService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=LandingPagePublic, status_code=status.HTTP_201_CREATED)
async def create_landing_page(
    payload: LandingPageCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    page = await service.create_page(organization_id, **payload.model_dump())
    return LandingPagePublic.model_validate(page)


@router.get("", response_model=dict)
async def list_landing_pages(
    campaign_id: uuid.UUID | None = None,
    status_filter: LandingPageStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    pages, total = await service.list_pages(
        organization_id, campaign_id=campaign_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [LandingPagePublic.model_validate(p) for p in pages],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{page_id}", response_model=LandingPagePublic)
async def get_landing_page(
    page_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    page = await service.get_page(page_id, organization_id)
    return LandingPagePublic.model_validate(page)


@router.patch("/{page_id}", response_model=LandingPagePublic)
async def update_landing_page(
    page_id: uuid.UUID,
    payload: LandingPageUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    page = await service.update_page(page_id, organization_id, **payload.model_dump(exclude_unset=True))
    return LandingPagePublic.model_validate(page)


@router.post("/{page_id}/publish", response_model=LandingPagePublic)
async def publish_landing_page(
    page_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    page = await service.publish_page(page_id, organization_id)
    return LandingPagePublic.model_validate(page)


@router.post("/{page_id}/archive", response_model=LandingPagePublic)
async def archive_landing_page(
    page_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    page = await service.archive_page(page_id, organization_id)
    return LandingPagePublic.model_validate(page)


@router.post("/{page_id}/views", response_model=LandingPageViewPublic, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_PUBLIC_VIEW)
async def record_view(
    page_id: uuid.UUID,
    payload: LandingPageViewCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Public-facing tracking beacon — deliberately carries no auth
    dependency at all (no JWT, no organization_id) since it's invoked by
    an anonymous visitor's browser on the published landing page itself,
    not by a logged-in ERP user. The page is resolved by its UUID alone.

    Because it is unauthenticated and writes a row per call, it is the one
    endpoint an anonymous client can flood to inflate view analytics /
    exhaust storage; a per-IP `@limiter.limit` (the only rate-limit
    mechanism wired in this app — there is no global SlowAPI middleware)
    bounds that abuse while leaving normal one-per-page-load tracking
    untouched. `request: Request` is required by slowapi's key function.
    """
    service = LandingPageService(db)
    view = await service.record_public_view(page_id, **payload.model_dump())
    return LandingPageViewPublic.model_validate(view)


@router.get("/{page_id}/views", response_model=dict)
async def list_views(
    page_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    views, total = await service.list_views(page_id, organization_id, skip=skip, limit=limit)
    return {
        "items": [LandingPageViewPublic.model_validate(v) for v in views],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{page_id}/stats", response_model=LandingPageStatsResponse)
async def get_stats(
    page_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("marketing.landing_pages.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LandingPageService(db)
    stats = await service.get_stats(page_id, organization_id)
    return LandingPageStatsResponse(**stats)
