import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.enrollment.schemas import (
    EnrollmentCreateRequest,
    EnrollmentPublic,
    EnrollmentStatusChangeRequest,
)
from modules.lms.enrollment.service import EnrollmentService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=list[EnrollmentPublic])
async def list_my_enrollments(
    student: Student = Depends(get_current_student), db: AsyncSession = Depends(get_db)
):
    service = EnrollmentService(db)
    enrollments = await service.list_for_student(student.id, student.organization_id)
    return [EnrollmentPublic.model_validate(e) for e in enrollments]


@router.post("", response_model=EnrollmentPublic, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    payload: EnrollmentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.enrollment.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EnrollmentService(db)
    enrollment = await service.create_enrollment(
        organization_id, payload.student_id, payload.course_id, payload.enrolled_on
    )
    return EnrollmentPublic.model_validate(enrollment)


@router.get("/by-student/{student_id}", response_model=list[EnrollmentPublic])
async def list_enrollments_for_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.enrollment.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EnrollmentService(db)
    enrollments = await service.list_for_student(student_id, organization_id)
    return [EnrollmentPublic.model_validate(e) for e in enrollments]


@router.get("/by-course/{course_id}", response_model=list[EnrollmentPublic])
async def list_enrollments_for_course(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.enrollment.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EnrollmentService(db)
    enrollments = await service.list_for_course(course_id, organization_id)
    return [EnrollmentPublic.model_validate(e) for e in enrollments]


@router.get("/{enrollment_id}", response_model=EnrollmentPublic)
async def get_enrollment(
    enrollment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.enrollment.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EnrollmentService(db)
    enrollment = await service.get_enrollment(enrollment_id, organization_id)
    return EnrollmentPublic.model_validate(enrollment)


@router.post("/{enrollment_id}/status", response_model=EnrollmentPublic)
async def change_enrollment_status(
    enrollment_id: uuid.UUID,
    payload: EnrollmentStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.enrollment.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EnrollmentService(db)
    enrollment = await service.change_status(enrollment_id, organization_id, payload.status)
    return EnrollmentPublic.model_validate(enrollment)
