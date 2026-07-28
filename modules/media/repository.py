import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.media.models import Album, MediaAsset, MediaAssetStatus


class AlbumRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Album:
        album = Album(**fields)
        self.db.add(album)
        await self.db.flush()
        await self.db.refresh(album)
        return album

    async def get_by_id(self, album_id: uuid.UUID, organization_id: uuid.UUID) -> Album | None:
        result = await self.db.execute(
            select(Album).where(Album.id == album_id, Album.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Album], int]:
        conditions = [Album.organization_id == organization_id]
        count_result = await self.db.execute(select(func.count()).select_from(Album).where(*conditions))
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Album).where(*conditions).order_by(Album.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, album: Album, **fields) -> Album:
        for key, value in fields.items():
            if value is not None:
                setattr(album, key, value)
        await self.db.flush()
        await self.db.refresh(album)
        return album

    async def delete(self, album: Album) -> None:
        await self.db.delete(album)
        await self.db.flush()


class MediaAssetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> MediaAsset:
        asset = MediaAsset(**fields)
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset

    async def get_by_id(self, asset_id: uuid.UUID, organization_id: uuid.UUID) -> MediaAsset | None:
        result = await self.db.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id, MediaAsset.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_album(
        self, album_id: uuid.UUID, status: MediaAssetStatus | None = None
    ) -> list[MediaAsset]:
        conditions = [MediaAsset.album_id == album_id]
        if status is not None:
            conditions.append(MediaAsset.status == status)
        result = await self.db.execute(
            select(MediaAsset).where(*conditions).order_by(MediaAsset.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_uploaded(self, asset: MediaAsset, size_bytes: int) -> MediaAsset:
        from datetime import datetime, timezone

        asset.status = MediaAssetStatus.UPLOADED
        asset.size_bytes = size_bytes
        asset.confirmed_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset

    async def update(self, asset: MediaAsset, **fields) -> MediaAsset:
        for key, value in fields.items():
            if value is not None:
                setattr(asset, key, value)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset

    async def delete(self, asset: MediaAsset) -> None:
        await self.db.delete(asset)
        await self.db.flush()
