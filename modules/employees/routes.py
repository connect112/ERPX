import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.employees.dependencies import get_current_employee
from modules.employees.models import Employee, EmploymentStatus
from modules.employees.schemas import (
    EmployeeCreateRequest,
    EmployeePublic,
    EmployeeStatusChangeRequest,
    EmployeeUpdateRequest,
    MessageResponse,
)
from modules.employees.service import EmployeeService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=EmployeePublic)
async def get_my_employee_profile(employee: Employee = Depends(get_current_employee)):
    """The calling user's own employee record. Ownership-gated via
    get_current_employee, no permission code — see that dependency's
    docstring."""
    return EmployeePublic.model_validate(employee)


@router.post("", response_model=EmployeePublic, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    employee = await service.create_employee(organization_id, **payload.model_dump())
    return EmployeePublic.model_validate(employee)


@router.get("", response_model=dict)
async def list_employees(
    department_id: uuid.UUID | None = None,
    designation_id: uuid.UUID | None = None,
    employment_status: EmploymentStatus | None = None,
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    employees, total = await service.list_employees(
        organization_id,
        department_id=department_id,
        designation_id=designation_id,
        employment_status=employment_status,
        search=search,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [EmployeePublic.model_validate(e) for e in employees],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{employee_id}", response_model=EmployeePublic)
async def get_employee(
    employee_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    employee = await service.get_employee(employee_id, organization_id)
    return EmployeePublic.model_validate(employee)


@router.get("/{employee_id}/direct-reports", response_model=list[EmployeePublic])
async def list_direct_reports(
    employee_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    reports = await service.list_direct_reports(employee_id, organization_id)
    return [EmployeePublic.model_validate(e) for e in reports]


@router.patch("/{employee_id}", response_model=EmployeePublic)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    employee = await service.update_employee(
        employee_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return EmployeePublic.model_validate(employee)


@router.post("/{employee_id}/status", response_model=EmployeePublic)
async def change_employee_status(
    employee_id: uuid.UUID,
    payload: EmployeeStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    employee = await service.change_status(
        employee_id, organization_id, payload.employment_status, payload.date_of_exit
    )
    return EmployeePublic.model_validate(employee)


@router.delete("/{employee_id}", response_model=MessageResponse)
async def delete_employee(
    employee_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EmployeeService(db)
    await service.delete_employee(employee_id, organization_id)
    return MessageResponse(message="Employee deleted successfully.")


@router.post("/{employee_id}/invite", response_model=EmployeePublic)
async def invite_employee(
    employee_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("employees.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Create employee-portal login access for an existing HR record — see
    EmployeeService.invite_employee's docstring for why this didn't
    already exist."""
    service = EmployeeService(db)
    employee = await service.invite_employee(employee_id, organization_id)
    return EmployeePublic.model_validate(employee)
