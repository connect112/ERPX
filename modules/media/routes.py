import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.media.schemas import (
    AlbumCreateRequest,
    AlbumListResponse,
    AlbumPublic,
    AlbumUpdateRequest,
    AssetDownloadResponse,
    AssetUpdateRequest,
    AssetUploadRequest,
    AssetUploadResponse,
    MediaAssetPublic,
    MessageResponse,
)
from modules.media.service import AlbumService, MediaAssetService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Albums ----


@router.post("/albums", response_model=AlbumPublic, status_code=status.HTTP_201_CREATED)
async def create_album(
    payload: AlbumCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlbumService(db)
    album = await service.create_album(organization_id, created_by_user_id=user.id, **payload.model_dump())
    return AlbumPublic.model_validate(album)


@router.get("/albums", response_model=AlbumListResponse)
async def list_albums(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AlbumService(db)
    albums, total = await service.list_albums(organization_id, skip=skip, limit=limit)
    return AlbumListResponse(items=[AlbumPublic.model_validate(a) for a in albums], total=total)


@router.get("/albums/{album_id}", response_model=AlbumPublic)
async def get_album(
    album_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AlbumService(db)
    album = await service.get_album(album_id, organization_id)
    return AlbumPublic.model_validate(album)


@router.patch("/albums/{album_id}", response_model=AlbumPublic)
async def update_album(
    album_id: uuid.UUID,
    payload: AlbumUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlbumService(db)
    album = await service.update_album(
        album_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AlbumPublic.model_validate(album)


@router.delete("/albums/{album_id}", response_model=MessageResponse)
async def delete_album(
    album_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlbumService(db)
    await service.delete_album(album_id, organization_id)
    return MessageResponse(message="Album deleted successfully.")


# ---- Assets ----


@router.post("/albums/{album_id}/assets/presigned-upload", response_model=AssetUploadResponse)
async def request_asset_upload(
    album_id: uuid.UUID,
    payload: AssetUploadRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = MediaAssetService(db)
    asset, upload_url = await service.request_upload(
        organization_id,
        album_id,
        uploaded_by_user_id=user.id,
        filename=payload.filename,
        content_type=payload.content_type,
        caption=payload.caption,
    )
    return AssetUploadResponse(asset_id=asset.id, upload_url=upload_url)


@router.post("/assets/{asset_id}/confirm", response_model=MediaAssetPublic)
async def confirm_asset_upload(
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = MediaAssetService(db)
    asset = await service.confirm_upload(asset_id, organization_id)
    return MediaAssetPublic.model_validate(asset)


@router.get("/albums/{album_id}/assets", response_model=list[MediaAssetPublic])
async def list_album_assets(
    album_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.view")),
    db: AsyncSession = Depends(get_db),
):
    service = MediaAssetService(db)
    assets = await service.list_for_album(album_id, organization_id)
    return [MediaAssetPublic.model_validate(a) for a in assets]


@router.get("/assets/{asset_id}/download-url", response_model=AssetDownloadResponse)
async def get_asset_download_url(
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.view")),
    db: AsyncSession = Depends(get_db),
):
    service = MediaAssetService(db)
    url = await service.get_download_url(asset_id, organization_id)
    return AssetDownloadResponse(download_url=url)


@router.patch("/assets/{asset_id}", response_model=MediaAssetPublic)
async def update_asset_caption(
    asset_id: uuid.UUID,
    payload: AssetUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = MediaAssetService(db)
    asset = await service.update_caption(asset_id, organization_id, payload.caption)
    return MediaAssetPublic.model_validate(asset)


@router.delete("/assets/{asset_id}", response_model=MessageResponse)
async def delete_asset(
    asset_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("media.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = MediaAssetService(db)
    await service.delete_asset(asset_id, organization_id)
    return MessageResponse(message="Media asset deleted successfully.")
