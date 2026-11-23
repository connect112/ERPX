import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.examinations.viva.schemas import (
    MessageResponse,
    MyVivaPublic,
    VivaCreateRequest,
    VivaPublic,
    VivaResultPublic,
    VivaUpdateRequest,
    RecordVivaResultRequest,
    UpdateVivaResultRequest,
)
from modules.examinations.viva.service import VivaService
from modules.learning.scope import authorize_internship, authorize_scoped, has_permission, student_internship_ids
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/viva"
MANAGE = "examinations.viva.manage"
VIEW = "examinations.viva.view"


async def _auth(db, user, org, course_id, row_internship_id, level, deleting=False):
    await authorize_scoped(db, user, org, course_id, row_internship_id, level, manage_code=MANAGE, view_code=VIEW, deleting=deleting)


@router.post(_PREFIX, response_model=VivaPublic, status_code=status.HTTP_201_CREATED)
async def create_viva(
    course_id: uuid.UUID,
    payload: VivaCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await _auth(db, user, organization_id, course_id, payload.internship_id, "manage")
    service = VivaService(db)
    viva = await service.create_viva(course_id, organization_id, **payload.model_dump())
    return VivaPublic.model_validate(viva)


@router.get(_PREFIX, response_model=list[VivaPublic])
async def list_vivas(
    course_id: uuid.UUID,
    internship_id: uuid.UUID | None = Query(default=None, description="One internship's own viva (and, with include_course, the course-wide ones)"),
    include_course: bool = False,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if internship_id is not None:
        await authorize_internship(db, user, organization_id, internship_id, "view", course_id=course_id)
    else:
        await _auth(db, user, organization_id, course_id, None, "view")
    service = VivaService(db)
    viva = await service.list_vivas(course_id, organization_id, internship_id=internship_id, include_course=include_course)
    return [VivaPublic.model_validate(p) for p in viva]


@router.get(_PREFIX + "/me", response_model=list[MyVivaPublic])
async def my_vivas(
    course_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """The caller's own view: what applies to them (course-wide, and their internships') with their own result. Never anyone else's."""
    service = VivaService(db)
    if await service.course_repo.get_by_id(course_id, student.organization_id) is None:
        raise NotFoundError("Course", course_id)
    return [MyVivaPublic(**row) for row in await service.my_vivas(course_id, student)]


@router.get(_PREFIX + "/{viva_id}", response_model=VivaPublic)
async def get_viva(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.get_viva(viva_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, viva.internship_id, "view")
    return VivaPublic.model_validate(viva)


@router.patch(_PREFIX + "/{viva_id}", response_model=VivaPublic)
async def update_viva(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    payload: VivaUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.get_viva(viva_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, viva.internship_id, "manage")
    updated = await service.update_viva(viva_id, course_id, organization_id, **payload.model_dump(exclude_unset=True))
    return VivaPublic.model_validate(updated)


@router.delete(_PREFIX + "/{viva_id}", response_model=MessageResponse)
async def delete_viva(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.get_viva(viva_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, viva.internship_id, "manage", deleting=True)
    await service.delete_viva(viva_id, course_id, organization_id)
    return MessageResponse(message="Viva deleted successfully.")


@router.post(_PREFIX + "/{viva_id}/results", response_model=VivaResultPublic, status_code=status.HTTP_201_CREATED)
async def record_result(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    payload: RecordVivaResultRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.get_viva(viva_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, viva.internship_id, "manage")
    result = await service.record_result(viva_id, course_id, organization_id, payload.student_id, payload.score, payload.remarks, user.id)
    return VivaResultPublic.model_validate(result)


@router.put(_PREFIX + "/{viva_id}/results/{student_id}", response_model=VivaResultPublic)
async def update_result(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: UpdateVivaResultRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.get_viva(viva_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, viva.internship_id, "manage")
    result = await service.update_result(viva_id, course_id, organization_id, student_id, payload.score, payload.remarks, user.id)
    return VivaResultPublic.model_validate(result)


@router.get(_PREFIX + "/{viva_id}/results", response_model=list[VivaResultPublic])
async def list_results(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    internship_id: uuid.UUID | None = Query(default=None, description="Only this internship's students"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.get_viva(viva_id, course_id, organization_id)
    if internship_id is not None:
        if viva.internship_id not in (None, internship_id):
            raise NotFoundError("Viva", viva_id)
        await authorize_internship(db, user, organization_id, internship_id, "view", course_id=course_id)
    else:
        await _auth(db, user, organization_id, course_id, viva.internship_id, "view")
    rows = await service.list_results(viva_id, course_id, organization_id, internship_id=internship_id)
    return [VivaResultPublic(**r) for r in rows]
