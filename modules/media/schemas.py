import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.media.models import MediaAssetStatus


class AlbumCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None


class AlbumUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None


class AlbumPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    title: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlbumListResponse(BaseModel):
    items: list[AlbumPublic]
    total: int


class AssetUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=255)
    caption: str | None = Field(default=None, max_length=500)


class AssetUploadResponse(BaseModel):
    asset_id: uuid.UUID
    upload_url: str


class AssetUpdateRequest(BaseModel):
    caption: str | None = Field(default=None, max_length=500)


class MediaAssetPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    album_id: uuid.UUID
    uploaded_by_user_id: uuid.UUID | None
    filename: str
    content_type: str
    size_bytes: int | None
    caption: str | None
    status: MediaAssetStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetDownloadResponse(BaseModel):
    download_url: str


class MessageResponse(BaseModel):
    message: str
