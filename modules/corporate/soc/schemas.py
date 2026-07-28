import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.corporate.soc.models import IncidentSeverity, IncidentStatus, SOCServiceStatus, SOCServiceType


class SOCServiceCreateRequest(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    service_type: SOCServiceType
    sla_response_time_minutes: int | None = Field(default=None, ge=1)
    start_date: date
    end_date: date | None = None
    notes: str | None = None


class SOCServiceUpdateRequest(BaseModel):
    sla_response_time_minutes: int | None = Field(default=None, ge=1)
    status: SOCServiceStatus | None = None
    end_date: date | None = None
    notes: str | None = None


class SOCServicePublic(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID | None
    service_type: SOCServiceType
    sla_response_time_minutes: int | None
    status: SOCServiceStatus
    start_date: date
    end_date: date | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SOCIncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    severity: IncidentSeverity
    description: str = Field(..., min_length=2)
    detected_at: datetime
    assigned_to_employee_id: uuid.UUID | None = None


class SOCIncidentUpdateRequest(BaseModel):
    status: IncidentStatus | None = None
    assigned_to_employee_id: uuid.UUID | None = None
    resolved_at: datetime | None = None


class SOCIncidentPublic(BaseModel):
    id: uuid.UUID
    soc_service_id: uuid.UUID
    assigned_to_employee_id: uuid.UUID | None
    title: str
    severity: IncidentSeverity
    description: str
    status: IncidentStatus
    detected_at: datetime
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
