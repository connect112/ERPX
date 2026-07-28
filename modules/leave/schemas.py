import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.leave.models import LeaveApplicationStatus


class LeaveTypeCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    annual_quota: float = Field(..., ge=0)
    is_paid: bool = True
    carry_forward_allowed: bool = False
    max_carry_forward_days: float | None = Field(default=None, ge=0)


class LeaveTypeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    annual_quota: float | None = Field(default=None, ge=0)
    is_paid: bool | None = None
    carry_forward_allowed: bool | None = None
    max_carry_forward_days: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class LeaveTypePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    annual_quota: float
    is_paid: bool
    carry_forward_allowed: bool
    max_carry_forward_days: float | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaveApplicationCreateRequest(BaseModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=2)


class LeaveApplicationRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=2)


class LeaveApplicationPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    approved_by_user_id: uuid.UUID | None
    start_date: date
    end_date: date
    number_of_days: int
    reason: str
    status: LeaveApplicationStatus
    rejection_reason: str | None
    approved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaveBalanceResponse(BaseModel):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_type_name: str
    year: int
    annual_quota: float
    days_used: float
    days_pending: float
    balance: float


class MessageResponse(BaseModel):
    message: str
