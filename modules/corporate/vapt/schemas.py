import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.corporate.vapt.models import (
    FindingSeverity,
    FindingStatus,
    VAPTEngagementStatus,
    VAPTEngagementType,
)


class VAPTEngagementCreateRequest(BaseModel):
    project_id: uuid.UUID
    scope_description: str = Field(..., min_length=2)
    engagement_type: VAPTEngagementType
    methodology: str | None = None
    lead_tester_employee_id: uuid.UUID | None = None
    start_date: date
    end_date: date | None = None


class VAPTEngagementUpdateRequest(BaseModel):
    scope_description: str | None = None
    methodology: str | None = None
    lead_tester_employee_id: uuid.UUID | None = None
    status: VAPTEngagementStatus | None = None
    start_date: date | None = None
    end_date: date | None = None


class VAPTEngagementPublic(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    lead_tester_employee_id: uuid.UUID | None
    scope_description: str
    engagement_type: VAPTEngagementType
    methodology: str | None
    status: VAPTEngagementStatus
    start_date: date
    end_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VAPTFindingCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    severity: FindingSeverity
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    description: str = Field(..., min_length=2)
    recommendation: str = Field(..., min_length=2)
    reported_date: date


class VAPTFindingUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    severity: FindingSeverity | None = None
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    description: str | None = None
    recommendation: str | None = None
    status: FindingStatus | None = None
    closed_date: date | None = None


class VAPTFindingPublic(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    title: str
    severity: FindingSeverity
    cvss_score: float | None
    description: str
    recommendation: str
    status: FindingStatus
    reported_date: date
    closed_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VAPTFindingsSummaryResponse(BaseModel):
    engagement_id: uuid.UUID
    total_findings: int
    open_findings: int
    by_severity: dict[str, int]


class MessageResponse(BaseModel):
    message: str
