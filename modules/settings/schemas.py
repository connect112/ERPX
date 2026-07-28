import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# Default settings applied to every newly created organization. Modules
# read these via GET /settings/{organization_id}/{key} rather than each
# growing bespoke config columns.
DEFAULT_ORGANIZATION_SETTINGS: dict[str, str] = {
    "timezone": "Asia/Kolkata",
    "currency": "INR",
    "date_format": "DD/MM/YYYY",
    "fiscal_year_start_month": "4",
    "week_start_day": "monday",
}


class SettingUpsertRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=150)
    value: str = Field(..., max_length=10000)


class SettingPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    key: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
