import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.documents.models import DocumentStatus


class DocumentUploadRequest(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: uuid.UUID | None = None
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=255)


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    upload_url: str


class DocumentPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    uploaded_by_user_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    filename: str
    content_type: str
    size_bytes: int | None
    status: DocumentStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentDownloadResponse(BaseModel):
    download_url: str


class MessageResponse(BaseModel):
    message: str
