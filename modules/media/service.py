import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.media.models import Album, MediaAsset, MediaAssetStatus
from modules.media.repository import AlbumRepository, MediaAssetRepository
from packages.storage.client import get_storage_client

logger = get_logger(__name__)

MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class AlbumService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AlbumRepository(db)
        self.asset_repo = MediaAssetRepository(db)
        self.storage = get_storage_client()

    async def create_album(self, organization_id: uuid.UUID, **fields) -> Album:
        album = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("media_album_created", album_id=str(album.id))
        return album

    async def get_album(self, album_id: uuid.UUID, organization_id: uuid.UUID) -> Album:
        album = await self.repo.get_by_id(album_id, organization_id)
        if not album:
            raise NotFoundError("Album", album_id)
        return album

    async def list_albums(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_album(self, album_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Album:
        album = await self.get_album(album_id, organization_id)
        updated = await self.repo.update(album, **fields)
        logger.info("media_album_updated", album_id=str(album_id))
        return updated

    async def delete_album(self, album_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        album = await self.get_album(album_id, organization_id)
        assets = await self.asset_repo.list_for_album(album_id)
        for asset in assets:
            if asset.status == MediaAssetStatus.UPLOADED:
                await self.storage.delete_object(asset.storage_key)
        await self.repo.delete(album)
        logger.info("media_album_deleted", album_id=str(album_id), assets_removed=len(assets))


class MediaAssetService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MediaAssetRepository(db)
        self.album_repo = AlbumRepository(db)
        self.storage = get_storage_client()

    async def request_upload(
        self,
        organization_id: uuid.UUID,
        album_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        filename: str,
        content_type: str,
        caption: str | None = None,
    ) -> tuple[MediaAsset, str]:
        album = await self.album_repo.get_by_id(album_id, organization_id)
        if not album:
            raise NotFoundError("Album", album_id)

        await self.storage.ensure_bucket()

        object_key = f"{organization_id}/media/{album_id}/{uuid.uuid4()}-{filename}"
        asset = await self.repo.create(
            organization_id=organization_id,
            album_id=album_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            content_type=content_type,
            storage_key=object_key,
            caption=caption,
            status=MediaAssetStatus.PENDING,
        )
        upload_url = self.storage.presigned_upload_url(object_key, content_type)
        logger.info("media_asset_upload_requested", asset_id=str(asset.id), album_id=str(album_id))
        return asset, upload_url

    async def confirm_upload(self, asset_id: uuid.UUID, organization_id: uuid.UUID) -> MediaAsset:
        asset = await self.repo.get_by_id(asset_id, organization_id)
        if not asset:
            raise NotFoundError("Media asset", asset_id)
        if asset.status == MediaAssetStatus.UPLOADED:
            return asset

        exists = await self.storage.object_exists(asset.storage_key)
        if not exists:
            raise ValidationError(
                "The file was not found in storage. Retry the upload before confirming."
            )

        size_bytes = await self.storage.object_size(asset.storage_key)
        if size_bytes > MAX_UPLOAD_SIZE_BYTES:
            await self.storage.delete_object(asset.storage_key)
            await self.repo.delete(asset)
            raise ValidationError(
                f"File exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB upload limit."
            )

        asset = await self.repo.mark_uploaded(asset, size_bytes=size_bytes)
        logger.info("media_asset_upload_confirmed", asset_id=str(asset_id))
        return asset

    async def list_for_album(self, album_id: uuid.UUID, organization_id: uuid.UUID) -> list[MediaAsset]:
        album = await self.album_repo.get_by_id(album_id, organization_id)
        if not album:
            raise NotFoundError("Album", album_id)
        return await self.repo.list_for_album(album_id, status=MediaAssetStatus.UPLOADED)

    async def get_download_url(self, asset_id: uuid.UUID, organization_id: uuid.UUID) -> str:
        asset = await self.repo.get_by_id(asset_id, organization_id)
        if not asset or asset.status != MediaAssetStatus.UPLOADED:
            raise NotFoundError("Media asset", asset_id)
        return self.storage.presigned_download_url(asset.storage_key)

    async def update_caption(
        self, asset_id: uuid.UUID, organization_id: uuid.UUID, caption: str | None
    ) -> MediaAsset:
        asset = await self.repo.get_by_id(asset_id, organization_id)
        if not asset:
            raise NotFoundError("Media asset", asset_id)
        asset.caption = caption
        await self.db.flush()
        await self.db.refresh(asset)
        logger.info("media_asset_caption_updated", asset_id=str(asset_id))
        return asset

    async def delete_asset(self, asset_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        asset = await self.repo.get_by_id(asset_id, organization_id)
        if not asset:
            raise NotFoundError("Media asset", asset_id)
        if asset.status == MediaAssetStatus.UPLOADED:
            await self.storage.delete_object(asset.storage_key)
        await self.repo.delete(asset)
        logger.info("media_asset_deleted", asset_id=str(asset_id))
