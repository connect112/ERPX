import uuid
from datetime import datetime

from pydantic import BaseModel

from modules.backups.models import BackupStatus


class BackupJobPublic(BaseModel):
    id: uuid.UUID
    triggered_by_user_id: uuid.UUID | None
    status: BackupStatus
    storage_key: str | None
    size_bytes: int | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupJobListResponse(BaseModel):
    items: list[BackupJobPublic]
    total: int


class BackupDownloadResponse(BaseModel):
    download_url: str
