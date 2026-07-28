import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.assets.models import AssetStatus, DepreciationMethod, DepreciationRunStatus


class AssetCategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    default_useful_life_years: int = Field(..., ge=1)
    default_depreciation_method: DepreciationMethod = DepreciationMethod.STRAIGHT_LINE


class AssetCategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    default_useful_life_years: int | None = Field(default=None, ge=1)
    default_depreciation_method: DepreciationMethod | None = None
    is_active: bool | None = None


class AssetCategoryPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    default_useful_life_years: int
    default_depreciation_method: DepreciationMethod
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetCreateRequest(BaseModel):
    asset_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=255)
    category_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    assigned_to_employee_id: uuid.UUID | None = None
    asset_account_id: uuid.UUID
    accumulated_depreciation_account_id: uuid.UUID
    depreciation_expense_account_id: uuid.UUID
    description: str | None = None
    location: str | None = None
    purchase_date: date
    purchase_cost: float = Field(..., gt=0)
    salvage_value: float = Field(default=0, ge=0)
    useful_life_years: int = Field(..., ge=1)
    depreciation_method: DepreciationMethod = DepreciationMethod.STRAIGHT_LINE
    notes: str | None = None


class AssetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    category_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    assigned_to_employee_id: uuid.UUID | None = None
    description: str | None = None
    location: str | None = None
    status: AssetStatus | None = None
    notes: str | None = None


class AssetPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    category_id: uuid.UUID | None
    assigned_to_employee_id: uuid.UUID | None
    asset_account_id: uuid.UUID
    accumulated_depreciation_account_id: uuid.UUID
    depreciation_expense_account_id: uuid.UUID
    disposal_journal_entry_id: uuid.UUID | None
    asset_code: str
    name: str
    description: str | None
    location: str | None
    purchase_date: date
    purchase_cost: float
    salvage_value: float
    useful_life_years: int
    depreciation_method: DepreciationMethod
    status: AssetStatus
    disposal_date: date | None
    disposal_amount: float | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetNetBookValueResponse(BaseModel):
    asset_id: uuid.UUID
    as_of_date: date
    purchase_cost: float
    accumulated_depreciation: float
    net_book_value: float


class DepreciationRunGenerateRequest(BaseModel):
    period_year: int = Field(..., ge=2000, le=2100)
    period_month: int = Field(..., ge=1, le=12)
    run_date: date


class DepreciationEntryPublic(BaseModel):
    id: uuid.UUID
    depreciation_run_id: uuid.UUID
    asset_id: uuid.UUID
    depreciation_amount: float
    accumulated_depreciation: float
    net_book_value: float
    created_at: datetime

    model_config = {"from_attributes": True}


class DepreciationRunPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    period_year: int
    period_month: int
    run_date: date
    status: DepreciationRunStatus
    total_depreciation_amount: float
    posted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DepreciationRunGenerationResult(BaseModel):
    run: DepreciationRunPublic
    assets_processed: int
    assets_fully_depreciated_skipped: list[uuid.UUID]


class DisposeAssetRequest(BaseModel):
    disposal_date: date
    disposal_amount: float = Field(..., ge=0)
    cash_account_id: uuid.UUID
    gain_loss_account_id: uuid.UUID


class MessageResponse(BaseModel):
    message: str
