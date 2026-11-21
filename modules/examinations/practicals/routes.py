import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.examinations.practicals.schemas import (
    MessageResponse,
    MyPracticalPublic,
    PracticalCreateRequest,
    PracticalPublic,
    PracticalResultPublic,
    PracticalUpdateRequest,
    RecordPracticalResultRequest,
    UpdatePracticalResultRequest,
)
from modules.examinations.practicals.service import PracticalService
from modules.learning.scope import authorize_internship, authorize_scoped, has_permission, student_internship_ids
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/practicals"
MANAGE = "examinations.practicals.manage"
VIEW = "examinations.practicals.view"


async def _auth(db, user, org, course_id, row_internship_id, level, deleting=False):
    await authorize_scoped(db, user, org, course_id, row_internship_id, level, manage_code=MANAGE, view_code=VIEW, deleting=deleting)


@router.post(_PREFIX, response_model=PracticalPublic, status_code=status.HTTP_201_CREATED)
async def create_practical(
    course_id: uuid.UUID,
    payload: PracticalCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await _auth(db, user, organization_id, course_id, payload.internship_id, "manage")
    service = PracticalService(db)
    practical = await service.create_practical(course_id, organization_id, **payload.model_dump())
    return PracticalPublic.model_validate(practical)


@router.get(_PREFIX, response_model=list[PracticalPublic])
async def list_practicals(
    course_id: uuid.UUID,
    internship_id: uuid.UUID | None = Query(default=None, description="One internship's own practicals (and, with include_course, the course-wide ones)"),
    include_course: bool = False,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if internship_id is not None:
        await authorize_internship(db, user, organization_id, internship_id, "view", course_id=course_id)
    else:
        await _auth(db, user, organization_id, course_id, None, "view")
    service = PracticalService(db)
    practicals = await service.list_practicals(course_id, organization_id, internship_id=internship_id, include_course=include_course)
    return [PracticalPublic.model_validate(p) for p in practicals]


@router.get(_PREFIX + "/me", response_model=list[MyPracticalPublic])
async def my_practicals(
    course_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """The caller's own view: what applies to them (course-wide, and their internships') with their own result. Never anyone else's."""
    service = PracticalService(db)
    if await service.course_repo.get_by_id(course_id, student.organization_id) is None:
        raise NotFoundError("Course", course_id)
    return [MyPracticalPublic(**row) for row in await service.my_practicals(course_id, student)]


@router.get(_PREFIX + "/{practical_id}", response_model=PracticalPublic)
async def get_practical(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.get_practical(practical_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, practical.internship_id, "view")
    return PracticalPublic.model_validate(practical)


@router.patch(_PREFIX + "/{practical_id}", response_model=PracticalPublic)
async def update_practical(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    payload: PracticalUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.get_practical(practical_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, practical.internship_id, "manage")
    updated = await service.update_practical(practical_id, course_id, organization_id, **payload.model_dump(exclude_unset=True))
    return PracticalPublic.model_validate(updated)


@router.delete(_PREFIX + "/{practical_id}", response_model=MessageResponse)
async def delete_practical(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.get_practical(practical_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, practical.internship_id, "manage", deleting=True)
    await service.delete_practical(practical_id, course_id, organization_id)
    return MessageResponse(message="Practical exam deleted successfully.")


@router.post(_PREFIX + "/{practical_id}/results", response_model=PracticalResultPublic, status_code=status.HTTP_201_CREATED)
async def record_result(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    payload: RecordPracticalResultRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.get_practical(practical_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, practical.internship_id, "manage")
    result = await service.record_result(practical_id, course_id, organization_id, payload.student_id, payload.score, payload.remarks, user.id)
    return PracticalResultPublic.model_validate(result)


@router.put(_PREFIX + "/{practical_id}/results/{student_id}", response_model=PracticalResultPublic)
async def update_result(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    student_id: uuid.UUID,
    payload: UpdatePracticalResultRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.get_practical(practical_id, course_id, organization_id)
    await _auth(db, user, organization_id, course_id, practical.internship_id, "manage")
    result = await service.update_result(practical_id, course_id, organization_id, student_id, payload.score, payload.remarks, user.id)
    return PracticalResultPublic.model_validate(result)


@router.get(_PREFIX + "/{practical_id}/results", response_model=list[PracticalResultPublic])
async def list_results(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    internship_id: uuid.UUID | None = Query(default=None, description="Only this internship's students"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.get_practical(practical_id, course_id, organization_id)
    if internship_id is not None:
        if practical.internship_id not in (None, internship_id):
            raise NotFoundError("Practical exam", practical_id)
        await authorize_internship(db, user, organization_id, internship_id, "view", course_id=course_id)
    else:
        await _auth(db, user, organization_id, course_id, practical.internship_id, "view")
    rows = await service.list_results(practical_id, course_id, organization_id, internship_id=internship_id)
    return [PracticalResultPublic(**r) for r in rows]
