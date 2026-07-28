import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.attendance.models import AttendanceStatus
from modules.attendance.schemas import (
    AttendanceRecordPublic,
    CheckInRequest,
    CheckOutRequest,
    MarkAttendanceRequest,
    MessageResponse,
    MonthlyAttendanceSummaryResponse,
    RegularizeAttendanceRequest,
    SelfCheckInRequest,
    SelfCheckOutRequest,
)
from modules.attendance.service import AttendanceService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.trainers.dependencies import get_current_trainer
from modules.trainers.models import Trainer
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/check-in/me", response_model=AttendanceRecordPublic, status_code=status.HTTP_201_CREATED)
async def self_check_in(
    payload: SelfCheckInRequest,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    record = await service.check_in(trainer.organization_id, trainer.employee_id, payload.check_in_time)
    return AttendanceRecordPublic.model_validate(record)


@router.post("/check-out/me", response_model=AttendanceRecordPublic)
async def self_check_out(
    payload: SelfCheckOutRequest,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    record = await service.check_out(trainer.organization_id, trainer.employee_id, payload.check_out_time)
    return AttendanceRecordPublic.model_validate(record)


@router.get("/me", response_model=dict)
async def list_my_attendance(
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    records, total = await service.list_for_employee(
        trainer.employee_id, trainer.organization_id, date_from=date_from, date_to=date_to, skip=skip, limit=limit
    )
    return {
        "items": [AttendanceRecordPublic.model_validate(r) for r in records],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post("/check-in", response_model=AttendanceRecordPublic, status_code=status.HTTP_201_CREATED)
async def check_in(
    payload: CheckInRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("attendance.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    record = await service.check_in(organization_id, payload.employee_id, payload.check_in_time)
    return AttendanceRecordPublic.model_validate(record)


@router.post("/check-out", response_model=AttendanceRecordPublic)
async def check_out(
    payload: CheckOutRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("attendance.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    record = await service.check_out(organization_id, payload.employee_id, payload.check_out_time)
    return AttendanceRecordPublic.model_validate(record)


@router.post("/mark", response_model=AttendanceRecordPublic)
async def mark_attendance(
    payload: MarkAttendanceRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("attendance.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    record = await service.mark_attendance(
        organization_id, payload.employee_id, payload.attendance_date, payload.status, payload.remarks
    )
    return AttendanceRecordPublic.model_validate(record)


@router.get("", response_model=dict)
async def list_attendance(
    branch_id: uuid.UUID | None = None,
    attendance_date: date | None = None,
    status_filter: AttendanceStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("attendance.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    records, total = await service.list_for_organization(
        organization_id, branch_id=branch_id, attendance_date=attendance_date, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [AttendanceRecordPublic.model_validate(r) for r in records],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/employees/{employee_id}", response_model=dict)
async def list_employee_attendance(
    employee_id: uuid.UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("attendance.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    records, total = await service.list_for_employee(
        employee_id, organization_id, date_from=date_from, date_to=date_to, skip=skip, limit=limit
    )
    return {
        "items": [AttendanceRecordPublic.model_validate(r) for r in records],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/employees/{employee_id}/summary", response_model=MonthlyAttendanceSummaryResponse)
async def get_monthly_summary(
    employee_id: uuid.UUID,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("attendance.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    summary = await service.monthly_summary(employee_id, organization_id, year, month)
    return MonthlyAttendanceSummaryResponse(**summary)


@router.post("/{record_id}/regularize", response_model=AttendanceRecordPublic)
async def regularize_attendance(
    record_id: uuid.UUID,
    payload: RegularizeAttendanceRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("attendance.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AttendanceService(db)
    record = await service.regularize(record_id, organization_id, **payload.model_dump())
    return AttendanceRecordPublic.model_validate(record)
