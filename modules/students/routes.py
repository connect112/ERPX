import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.students.models import StudentStatus
from modules.students.schemas import (
    MessageResponse,
    StudentCreateRequest,
    StudentFromAdmissionRequest,
    StudentPublic,
    StudentStatusChangeRequest,
    StudentUpdateRequest,
)
from modules.students.dependencies import get_current_student
from modules.students.service import StudentService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=StudentPublic)
async def get_my_student_profile(student=Depends(get_current_student)):
    return StudentPublic.model_validate(student)


@router.post("", response_model=StudentPublic, status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("students.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StudentService(db)
    student = await service.create_student(organization_id, **payload.model_dump())
    return StudentPublic.model_validate(student)


@router.post(
    "/from-admission/{admission_id}",
    response_model=StudentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_student_from_admission(
    admission_id: uuid.UUID,
    payload: StudentFromAdmissionRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("students.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StudentService(db)
    student = await service.create_from_admission(
        admission_id, organization_id, payload.branch_id, payload.enrollment_date
    )
    return StudentPublic.model_validate(student)


@router.get("", response_model=dict)
async def list_students(
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("students.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StudentService(db)
    students, total = await service.list_students(
        organization_id, status=status_filter, search=search, skip=skip, limit=limit
    )
    return {
        "items": [StudentPublic.model_validate(s) for s in students],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{student_id}", response_model=StudentPublic)
async def get_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("students.view")),
    db: AsyncSession = Depends(get_db),
):
    service = StudentService(db)
    student = await service.get_student(student_id, organization_id)
    return StudentPublic.model_validate(student)


@router.patch("/{student_id}", response_model=StudentPublic)
async def update_student(
    student_id: uuid.UUID,
    payload: StudentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("students.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StudentService(db)
    student = await service.update_student(
        student_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return StudentPublic.model_validate(student)


@router.post("/{student_id}/status", response_model=StudentPublic)
async def change_student_status(
    student_id: uuid.UUID,
    payload: StudentStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("students.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StudentService(db)
    student = await service.change_status(student_id, organization_id, payload.status, payload.notes)
    return StudentPublic.model_validate(student)


@router.delete("/{student_id}", response_model=MessageResponse)
async def delete_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("students.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = StudentService(db)
    await service.delete_student(student_id, organization_id)
    return MessageResponse(message="Student deleted successfully.")
