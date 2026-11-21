import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.courses.resources.models import ResourceType


class ResourceCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    resource_type: ResourceType = ResourceType.OTHER
    file_url: str = Field(..., min_length=1, max_length=512)
    is_downloadable: bool = True


class ResourceUpdateRequest(BaseModel):
    title: str | None = None
    resource_type: ResourceType | None = None
    file_url: str | None = None
    is_downloadable: bool | None = None


class ResourcePublic(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    resource_type: ResourceType
    file_url: str
    is_downloadable: bool
    # an uploaded file (downloaded through the authenticated route) rather than a link
    is_upload: bool = False
    original_filename: str | None = None
    size_bytes: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


class ResourceDownload(BaseModel):
    """A short-lived link to the stored file."""

    url: str
    filename: str
