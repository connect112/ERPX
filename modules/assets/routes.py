import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.assets.models import AssetStatus
from modules.assets.schemas import (
    AssetCategoryCreateRequest,
    AssetCategoryPublic,
    AssetCategoryUpdateRequest,
    AssetCreateRequest,
    AssetNetBookValueResponse,
    AssetPublic,
    AssetUpdateRequest,
    DepreciationEntryPublic,
    DepreciationRunGenerateRequest,
    DepreciationRunGenerationResult,
    DepreciationRunPublic,
    DisposeAssetRequest,
    MessageResponse,
)
from modules.assets.service import AssetCategoryService, AssetDisposalService, AssetService, DepreciationService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Asset Categories ----


@router.post("/categories", response_model=AssetCategoryPublic, status_code=status.HTTP_201_CREATED)
async def create_asset_category(
    payload: AssetCategoryCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetCategoryService(db)
    category = await service.create_category(organization_id, **payload.model_dump())
    return AssetCategoryPublic.model_validate(category)


@router.get("/categories", response_model=list[AssetCategoryPublic])
async def list_asset_categories(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetCategoryService(db)
    categories = await service.list_categories(organization_id, is_active)
    return [AssetCategoryPublic.model_validate(c) for c in categories]


@router.patch("/categories/{category_id}", response_model=AssetCategoryPublic)
async def update_asset_category(
    category_id: uuid.UUID,
    payload: AssetCategoryUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetCategoryService(db)
    category = await service.update_category(
        category_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AssetCategoryPublic.model_validate(category)


# ---- Assets ----


@router.post("", response_model=AssetPublic, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.create_asset(organization_id, **payload.model_dump())
    return AssetPublic.model_validate(asset)


@router.get("", response_model=dict)
async def list_assets(
    category_id: uuid.UUID | None = None,
    status_filter: AssetStatus | None = Query(default=None, alias="status"),
    assigned_to_employee_id: uuid.UUID | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    assets, total = await service.list_assets(
        organization_id,
        category_id=category_id,
        status=status_filter,
        assigned_to_employee_id=assigned_to_employee_id,
        search=search,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [AssetPublic.model_validate(a) for a in assets],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{asset_id}", response_model=AssetPublic)
async def get_asset(
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.get_asset(asset_id, organization_id)
    return AssetPublic.model_validate(asset)


@router.patch("/{asset_id}", response_model=AssetPublic)
async def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.update_asset(asset_id, organization_id, **payload.model_dump(exclude_unset=True))
    return AssetPublic.model_validate(asset)


@router.get("/{asset_id}/net-book-value", response_model=AssetNetBookValueResponse)
async def get_net_book_value(
    asset_id: uuid.UUID,
    as_of_date: date | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    nbv = await service.get_net_book_value(asset_id, organization_id, as_of_date)
    return AssetNetBookValueResponse(**nbv)


@router.post("/{asset_id}/dispose", response_model=AssetPublic)
async def dispose_asset(
    asset_id: uuid.UUID,
    payload: DisposeAssetRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.dispose")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetDisposalService(db)
    asset = await service.dispose_asset(asset_id, organization_id, created_by_user_id=user.id, **payload.model_dump())
    return AssetPublic.model_validate(asset)


# ---- Depreciation Runs ----


@router.post("/depreciation-runs", response_model=DepreciationRunGenerationResult, status_code=status.HTTP_201_CREATED)
async def generate_depreciation_run(
    payload: DepreciationRunGenerateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.depreciation.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DepreciationService(db)
    run, processed, skipped = await service.generate_run(
        organization_id, created_by_user_id=user.id, **payload.model_dump()
    )
    return DepreciationRunGenerationResult(
        run=DepreciationRunPublic.model_validate(run),
        assets_processed=processed,
        assets_fully_depreciated_skipped=skipped,
    )


@router.get("/depreciation-runs", response_model=dict)
async def list_depreciation_runs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.depreciation.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DepreciationService(db)
    runs, total = await service.list_runs(organization_id, skip=skip, limit=limit)
    return {
        "items": [DepreciationRunPublic.model_validate(r) for r in runs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/depreciation-runs/{run_id}", response_model=DepreciationRunPublic)
async def get_depreciation_run(
    run_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.depreciation.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DepreciationService(db)
    run = await service.get_run(run_id, organization_id)
    return DepreciationRunPublic.model_validate(run)


@router.get("/depreciation-runs/{run_id}/entries", response_model=list[DepreciationEntryPublic])
async def list_depreciation_entries(
    run_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.depreciation.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DepreciationService(db)
    entries = await service.list_entries(run_id, organization_id)
    return [DepreciationEntryPublic.model_validate(e) for e in entries]


@router.post("/depreciation-runs/{run_id}/post", response_model=DepreciationRunPublic)
async def post_depreciation_run(
    run_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.depreciation.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DepreciationService(db)
    run = await service.post_run(run_id, organization_id, created_by_user_id=user.id)
    return DepreciationRunPublic.model_validate(run)


@router.post("/depreciation-runs/{run_id}/cancel", response_model=DepreciationRunPublic)
async def cancel_depreciation_run(
    run_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("assets.depreciation.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DepreciationService(db)
    run = await service.cancel_run(run_id, organization_id)
    return DepreciationRunPublic.model_validate(run)
