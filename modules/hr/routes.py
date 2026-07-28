import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.hr.schemas import (
    DepartmentCreateRequest,
    DepartmentPublic,
    DepartmentUpdateRequest,
    DesignationCreateRequest,
    DesignationPublic,
    DesignationUpdateRequest,
    MessageResponse,
)
from modules.hr.service import DepartmentService, DesignationService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Departments ----


@router.post("/departments", response_model=DepartmentPublic, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.departments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DepartmentService(db)
    department = await service.create_department(organization_id, **payload.model_dump())
    return DepartmentPublic.model_validate(department)


@router.get("/departments", response_model=list[DepartmentPublic])
async def list_departments(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.departments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DepartmentService(db)
    departments = await service.list_departments(organization_id, is_active)
    return [DepartmentPublic.model_validate(d) for d in departments]


@router.get("/departments/{department_id}", response_model=DepartmentPublic)
async def get_department(
    department_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.departments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DepartmentService(db)
    department = await service.get_department(department_id, organization_id)
    return DepartmentPublic.model_validate(department)


@router.patch("/departments/{department_id}", response_model=DepartmentPublic)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.departments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DepartmentService(db)
    department = await service.update_department(
        department_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return DepartmentPublic.model_validate(department)


# ---- Designations ----


@router.post("/designations", response_model=DesignationPublic, status_code=status.HTTP_201_CREATED)
async def create_designation(
    payload: DesignationCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.designations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DesignationService(db)
    designation = await service.create_designation(organization_id, **payload.model_dump())
    return DesignationPublic.model_validate(designation)


@router.get("/designations", response_model=list[DesignationPublic])
async def list_designations(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.designations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DesignationService(db)
    designations = await service.list_designations(organization_id, is_active)
    return [DesignationPublic.model_validate(d) for d in designations]


@router.get("/designations/{designation_id}", response_model=DesignationPublic)
async def get_designation(
    designation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.designations.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DesignationService(db)
    designation = await service.get_designation(designation_id, organization_id)
    return DesignationPublic.model_validate(designation)


@router.patch("/designations/{designation_id}", response_model=DesignationPublic)
async def update_designation(
    designation_id: uuid.UUID,
    payload: DesignationUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("hr.designations.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DesignationService(db)
    designation = await service.update_designation(
        designation_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return DesignationPublic.model_validate(designation)
