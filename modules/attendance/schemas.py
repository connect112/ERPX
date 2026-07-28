import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.attendance.models import AttendanceStatus


class CheckInRequest(BaseModel):
    employee_id: uuid.UUID
    check_in_time: datetime | None = Field(
        default=None, description="Defaults to the current server time if omitted."
    )


class CheckOutRequest(BaseModel):
    employee_id: uuid.UUID
    check_out_time: datetime | None = Field(
        default=None, description="Defaults to the current server time if omitted."
    )


class SelfCheckInRequest(BaseModel):
    check_in_time: datetime | None = Field(
        default=None, description="Defaults to the current server time if omitted."
    )


class SelfCheckOutRequest(BaseModel):
    check_out_time: datetime | None = Field(
        default=None, description="Defaults to the current server time if omitted."
    )


class MarkAttendanceRequest(BaseModel):
    employee_id: uuid.UUID
    attendance_date: date
    status: AttendanceStatus
    remarks: str | None = None


class RegularizeAttendanceRequest(BaseModel):
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    status: AttendanceStatus | None = None
    regularization_reason: str = Field(..., min_length=2)


class AttendanceRecordPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID | None
    employee_id: uuid.UUID
    attendance_date: date
    check_in_time: datetime | None
    check_out_time: datetime | None
    work_hours: float | None
    status: AttendanceStatus
    is_regularized: bool
    regularization_reason: str | None
    remarks: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MonthlyAttendanceSummaryResponse(BaseModel):
    employee_id: uuid.UUID
    year: int
    month: int
    present_days: int
    absent_days: int
    half_days: int
    leave_days: int
    holiday_days: int
    week_off_days: int
    total_work_hours: float


class MessageResponse(BaseModel):
    message: str
