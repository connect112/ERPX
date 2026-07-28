import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.leave.models import LeaveApplicationStatus
from modules.leave.schemas import (
    LeaveApplicationCreateRequest,
    LeaveApplicationPublic,
    LeaveApplicationRejectRequest,
    LeaveBalanceResponse,
    LeaveTypeCreateRequest,
    LeaveTypePublic,
    LeaveTypeUpdateRequest,
    MessageResponse,
)
from modules.leave.service import LeaveApplicationService, LeaveTypeService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Leave Types ----


@router.post("/types", response_model=LeaveTypePublic, status_code=status.HTTP_201_CREATED)
async def create_leave_type(
    payload: LeaveTypeCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.types.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveTypeService(db)
    leave_type = await service.create_leave_type(organization_id, **payload.model_dump())
    return LeaveTypePublic.model_validate(leave_type)


@router.get("/types", response_model=list[LeaveTypePublic])
async def list_leave_types(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.types.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveTypeService(db)
    leave_types = await service.list_leave_types(organization_id, is_active)
    return [LeaveTypePublic.model_validate(lt) for lt in leave_types]


@router.patch("/types/{leave_type_id}", response_model=LeaveTypePublic)
async def update_leave_type(
    leave_type_id: uuid.UUID,
    payload: LeaveTypeUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.types.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveTypeService(db)
    leave_type = await service.update_leave_type(
        leave_type_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return LeaveTypePublic.model_validate(leave_type)


# ---- Leave Applications ----


@router.post("/applications", response_model=LeaveApplicationPublic, status_code=status.HTTP_201_CREATED)
async def apply_leave(
    payload: LeaveApplicationCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.apply")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    application = await service.apply_leave(organization_id, **payload.model_dump())
    return LeaveApplicationPublic.model_validate(application)


@router.get("/applications", response_model=dict)
async def list_applications(
    status_filter: LeaveApplicationStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    applications, total = await service.list_for_organization(
        organization_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [LeaveApplicationPublic.model_validate(a) for a in applications],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/applications/employees/{employee_id}", response_model=dict)
async def list_employee_applications(
    employee_id: uuid.UUID,
    leave_type_id: uuid.UUID | None = None,
    status_filter: LeaveApplicationStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    applications, total = await service.list_for_employee(
        employee_id, organization_id, leave_type_id=leave_type_id, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [LeaveApplicationPublic.model_validate(a) for a in applications],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/applications/{application_id}", response_model=LeaveApplicationPublic)
async def get_application(
    application_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    application = await service.get_application(application_id, organization_id)
    return LeaveApplicationPublic.model_validate(application)


@router.post("/applications/{application_id}/approve", response_model=LeaveApplicationPublic)
async def approve_application(
    application_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.approve")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    application = await service.approve_leave(application_id, organization_id, approved_by_user_id=user.id)
    return LeaveApplicationPublic.model_validate(application)


@router.post("/applications/{application_id}/reject", response_model=LeaveApplicationPublic)
async def reject_application(
    application_id: uuid.UUID,
    payload: LeaveApplicationRejectRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.approve")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    application = await service.reject_leave(application_id, organization_id, payload.rejection_reason)
    return LeaveApplicationPublic.model_validate(application)


@router.post("/applications/{application_id}/cancel", response_model=LeaveApplicationPublic)
async def cancel_application(
    application_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.apply")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    application = await service.cancel_leave(application_id, organization_id)
    return LeaveApplicationPublic.model_validate(application)


@router.get("/balances/employees/{employee_id}", response_model=list[LeaveBalanceResponse])
async def list_employee_balances(
    employee_id: uuid.UUID,
    year: int = Query(..., ge=2000, le=2100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("leave.applications.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LeaveApplicationService(db)
    balances = await service.list_balances_for_employee(employee_id, organization_id, year)
    return [LeaveBalanceResponse(**b) for b in balances]
