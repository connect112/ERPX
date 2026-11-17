import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.courses.models import Course, CourseType
from modules.courses.schemas import CourseAdminOut, CourseCreateRequest, CoursePublic, CourseUpdateRequest, LinkedInternship, MessageResponse
from modules.courses.service import CourseService
from modules.lms.enrollment.access import require_live_enrollment
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


async def _staff_view(db, user: User, organization_id: uuid.UUID, courses: list[Course]) -> list[CourseAdminOut]:
    """Courses as staff see them, with their linked internships (and the fee, under the rules in our_internships/course_links.py)."""
    from modules.our_internships.course_links import describe

    links = await describe(db, user, organization_id, courses)
    return [
        CourseAdminOut.model_validate({**CoursePublic.model_validate(c).model_dump(), "linked_internships": [LinkedInternship(**i) for i in links.get(c.id, [])]})
        for c in courses
    ]


@router.get("/{course_id}/me", response_model=CoursePublic)
async def get_my_course(
    course_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    await require_live_enrollment(db, student, course_id)
    service = CourseService(db)
    course = await service.get_course(course_id, student.organization_id)
    return CoursePublic.model_validate(course)


@router.post("/", response_model=CourseAdminOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseService(db)
    course = await service.create_course(organization_id, **payload.model_dump())
    return (await _staff_view(db, user, organization_id, [course]))[0]


@router.get("/", response_model=dict)
async def list_courses(
    category_id: uuid.UUID | None = None,
    is_published: bool | None = None,
    course_type: CourseType | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseService(db)
    courses, total = await service.list_courses(
        organization_id, category_id=category_id, is_published=is_published, skip=skip, limit=limit, course_type=course_type
    )
    return {
        "items": await _staff_view(db, user, organization_id, courses),
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{course_id}", response_model=CourseAdminOut)
async def get_course(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.view")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseService(db)
    course = await service.get_course(course_id, organization_id)
    return (await _staff_view(db, user, organization_id, [course]))[0]


@router.patch("/{course_id}", response_model=CourseAdminOut)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseService(db)
    course = await service.update_course(
        course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return (await _staff_view(db, user, organization_id, [course]))[0]


@router.post("/{course_id}/publish", response_model=CourseAdminOut)
async def publish_course(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseService(db)
    course = await service.publish_course(course_id, organization_id)
    return (await _staff_view(db, user, organization_id, [course]))[0]


@router.post("/{course_id}/unpublish", response_model=CourseAdminOut)
async def unpublish_course(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseService(db)
    course = await service.unpublish_course(course_id, organization_id)
    return (await _staff_view(db, user, organization_id, [course]))[0]


@router.delete("/{course_id}", response_model=MessageResponse)
async def delete_course(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("courses.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseService(db)
    await service.delete_course(course_id, organization_id)
    return MessageResponse(message="Course deleted successfully.")
