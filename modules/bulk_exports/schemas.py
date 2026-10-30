import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlaceholderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    example: str = ""
    custom: bool = False


class OptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value: str
    label: str


class PresetOut(BaseModel):
    label: str
    template: str


class SourceInfo(BaseModel):
    source: str
    label: str
    document_type: str
    scope_id: uuid.UUID | None
    scope_label: str
    extension: str | None
    placeholders: list[PlaceholderOut]
    zip_placeholders: list[PlaceholderOut]
    status_options: list[OptionOut]
    presets: list[PresetOut]
    folder_presets: list[PresetOut]
    default_zip_template: str
    max_items: int


class ItemOut(BaseModel):
    id: uuid.UUID
    title: str
    subtitle: str
    status: str | None


class ItemsPage(BaseModel):
    items: list[ItemOut]
    total: int
    page: int
    page_size: int


class Selection(BaseModel):
    """``selected``: exactly these ids (picked across any number of pages). ``filtered``: everything matching the search
    and status, except ``exclude_ids`` -- what "select all matching" means, without sending thousands of ids."""

    mode: Literal["selected", "filtered"]
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=20000)
    search: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, max_length=60)
    exclude_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20000)


class NamingOptions(BaseModel):
    filename_template: str = Field(max_length=200)
    folder_template: str | None = Field(default=None, max_length=200)
    zip_template: str | None = Field(default=None, max_length=200)


class PreviewRequest(BaseModel):
    source: str = Field(max_length=60)
    scope_id: uuid.UUID | None = None
    options: NamingOptions
    selection: Selection | None = None


class PreviewFile(BaseModel):
    id: uuid.UUID
    title: str
    path: str
    missing: list[str]


class PreviewOut(BaseModel):
    valid: bool
    error: str | None = None
    zip_filename: str | None = None
    total: int = 0
    files: list[PreviewFile] = []
    warnings: list[str] = []
    renamed_duplicates: int = 0


class JobCreateRequest(BaseModel):
    source: str = Field(max_length=60)
    scope_id: uuid.UUID | None = None
    selection: Selection
    options: NamingOptions


class FailureOut(BaseModel):
    id: str
    title: str
    error: str


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    source_label: str = ""
    scope_id: uuid.UUID | None
    scope_label: str
    status: str
    selection_mode: str
    options: dict
    total_items: int
    processed_items: int
    failed_items: int
    failures: list[FailureOut]
    zip_filename: str | None
    size_bytes: int | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None
    download_count: int


class DownloadOut(BaseModel):
    url: str
    filename: str
    expires_in_seconds: int
