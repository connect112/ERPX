import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    kind: str  # record | reference | protected | note
    text: str
    module: str | None = None
    record_id: str | None = None


class FileItem(BaseModel):
    id: str
    source: str
    source_label: str
    module: str
    backend: str  # object_storage | database
    name: str
    path: list[str]
    size_bytes: int
    content_type: str | None
    type_group: str
    created_at: datetime | None
    owner: str | None
    organization_id: uuid.UUID | None
    organization_name: str | None
    location: str
    status: str  # in_use | pending | orphan | missing_object | protected
    protected: bool
    protected_reason: str | None
    fingerprint: str | None = None
    is_large: bool = False
    previewable: str | None = None


class FolderItem(BaseModel):
    name: str
    path: list[str]
    file_count: int
    total_bytes: int


class FileListResponse(BaseModel):
    items: list[FileItem]
    folders: list[FolderItem]
    path: list[str]
    total: int
    page: int
    page_size: int
    total_bytes: int
    flat: bool
    # Everything inside the open folder (or every match of a search), including sub-folders.
    subtree_count: int
    subtree_bytes: int


class Analysis(BaseModel):
    item: FileItem
    verdict: str  # eligible | in_use | protected | not_deletable | missing
    can_delete: bool
    reasons: list[str]
    evidence: list[Evidence]


class DuplicateGroup(BaseModel):
    fingerprint: str
    size_bytes: int
    count: int
    wasted_bytes: int
    files: list[FileItem]


class SourceUsage(BaseModel):
    key: str
    label: str
    backend: str
    count: int
    bytes: int
    protected: bool


class TypeUsage(BaseModel):
    type_group: str
    count: int
    bytes: int


class FilesUsage(BaseModel):
    total_count: int
    total_bytes: int
    by_source: list[SourceUsage]
    by_type: list[TypeUsage]
    orphan_count: int
    orphan_bytes: int
    large_count: int
    large_bytes: int
    duplicate_groups: int
    duplicate_wasted_bytes: int
    protected_count: int
    protected_bytes: int
    trash_count: int
    trash_bytes: int


class UsageResponse(BaseModel):
    generated_at: datetime
    scope: str  # organization | platform
    files: FilesUsage
    can_delete: bool


class DeletionPreviewRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)


class DeletionPreviewResponse(BaseModel):
    items: list[Analysis]
    eligible_count: int
    blocked_count: int
    total_bytes: int
    confirm_text: str


class DeletionRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=3, max_length=1000)
    confirm_text: str


class TrashItem(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    source: str
    original_key: str
    filename: str
    content_type: str | None
    size_bytes: int
    reason: str
    deleted_by: str | None
    deleted_at: datetime
    purge_allowed_at: datetime
    can_purge: bool
    restored_at: datetime | None
    purged_at: datetime | None
    evidence: list[Evidence]


class TrashListResponse(BaseModel):
    items: list[TrashItem]
    total: int
    total_bytes: int
    min_days: int


class DeletionResult(BaseModel):
    moved: list[TrashItem]
    total_bytes: int


class RestoreRequest(BaseModel):
    pass


class PurgeRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    confirm_text: str


class DeletionLogItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    source: str
    object_key: str
    filename: str | None
    size_bytes: int | None
    user_email: str | None
    reason: str | None
    ip_address: str | None
    evidence: list[Evidence]
    trash_id: uuid.UUID | None


class DeletionLogResponse(BaseModel):
    items: list[DeletionLogItem]
    total: int


class PreviewResponse(BaseModel):
    kind: str | None
    mode: str  # url | content | none
    url: str | None
    content_type: str | None
    expires_in: int | None
    message: str | None = None


class ServerResponse(BaseModel):
    generated_at: datetime
    database: dict
    object_storage: dict
    host: dict
