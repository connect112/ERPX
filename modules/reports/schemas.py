import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.reports.models import ExportFormat, ReportExecutionStatus, ScheduleFrequency


class ReportDefinitionPublic(BaseModel):
    key: str
    name: str
    module: str
    description: str
    required_parameters: list[str]


class RunReportRequest(BaseModel):
    report_key: str = Field(..., min_length=1, max_length=100)
    parameters: dict = Field(default_factory=dict)
    export_format: ExportFormat = ExportFormat.JSON


class ReportExecutionPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    executed_by_user_id: uuid.UUID | None
    scheduled_report_id: uuid.UUID | None
    report_key: str
    parameters: dict
    export_format: ExportFormat
    status: ReportExecutionStatus
    row_count: int | None
    execution_time_ms: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunReportJSONResponse(BaseModel):
    execution_id: uuid.UUID
    title: str
    columns: list[str]
    rows: list[dict]
    row_count: int


class ScheduledReportCreateRequest(BaseModel):
    report_key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=2, max_length=255)
    parameters: dict = Field(default_factory=dict)
    export_format: ExportFormat = ExportFormat.EXCEL
    frequency: ScheduleFrequency
    recipient_emails: list[str] = Field(..., min_length=1)


class ScheduledReportUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    parameters: dict | None = None
    export_format: ExportFormat | None = None
    frequency: ScheduleFrequency | None = None
    recipient_emails: list[str] | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class ScheduledReportPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    report_key: str
    name: str
    parameters: dict
    export_format: ExportFormat
    frequency: ScheduleFrequency
    recipient_emails: list[str]
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
