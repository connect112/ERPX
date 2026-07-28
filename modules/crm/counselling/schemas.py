import uuid
from datetime import datetime

from pydantic import BaseModel

from modules.crm.counselling.models import CounsellingMode, CounsellingStatus


class CounsellingCreateRequest(BaseModel):
    counselor_user_id: uuid.UUID | None = None
    mode: CounsellingMode = CounsellingMode.PHONE
    scheduled_at: datetime
    notes: str | None = None


class CounsellingUpdateRequest(BaseModel):
    counselor_user_id: uuid.UUID | None = None
    mode: CounsellingMode | None = None
    status: CounsellingStatus | None = None
    scheduled_at: datetime | None = None
    recommended_course: str | None = None
    notes: str | None = None


class CounsellingCompleteRequest(BaseModel):
    recommended_course: str | None = None
    notes: str | None = None


class CounsellingPublic(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    counselor_user_id: uuid.UUID | None
    mode: CounsellingMode
    status: CounsellingStatus
    scheduled_at: datetime
    recommended_course: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
