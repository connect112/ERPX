import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authentication.dependencies import get_current_active_user
from modules.learning.scope import authorize_internship, has_permission, student_internship_ids
from modules.lms.discussions.models import DiscussionThread
from modules.lms.discussions.schemas import (
    LockRequest,
    MessageResponse,
    ReplyCreateRequest,
    ReplyPublic,
    ThreadCreateRequest,
    ThreadPublic,
)
from modules.lms.discussions.service import DiscussionService
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/discussions"
PARTICIPATE = "lms.discussions.participate"
MODERATE = "courses.manage"  # course authors moderate course-wide threads (no new permission code is needed)


async def _may_reach_internship(db: AsyncSession, user: User, organization_id: uuid.UUID, course_id: uuid.UUID, internship_id: uuid.UUID) -> bool:
    """A student with granted access on THAT internship, or staff with Our Internships access to it (instructors included)."""
    student = await StudentRepository(db).get_by_user_id(user.id)
    if student is not None and internship_id in await student_internship_ids(db, student, course_id):
        return True
    try:
        await authorize_internship(db, user, organization_id, internship_id, "view", course_id=course_id)
        return True
    except (AuthorizationError, NotFoundError):
        return False


async def _may_participate(db: AsyncSession, user: User, organization_id: uuid.UUID, course_id: uuid.UUID, internship_id: uuid.UUID | None) -> None:
    """Take part in discussions: the course permission (students hold it) for anything course-wide; for an internship's own thread, staff
    with Our Internships access to that internship (an instructor needs no course permission) or a student with the permission."""
    if await has_permission(db, user, PARTICIPATE):
        return
    if internship_id is not None and await StudentRepository(db).get_by_user_id(user.id) is None and await _may_reach_internship(db, user, organization_id, course_id, internship_id):
        return
    raise AuthorizationError(f"This action requires the following permission(s): {PARTICIPATE}")


async def _reachable_thread(db, user, organization_id, course_id, thread_id) -> DiscussionThread:
    """The thread, if the caller may see it. A cohort thread that is not theirs is "not found": its existence is not revealed."""
    service = DiscussionService(db)
    thread = await service.get_thread(thread_id, course_id, organization_id)
    if thread.internship_id is not None and not await _may_reach_internship(db, user, organization_id, course_id, thread.internship_id):
        raise NotFoundError("Discussion thread", thread_id)
    return thread


async def _out_threads(service: DiscussionService, threads) -> list[ThreadPublic]:
    names = await service.author_names({t.created_by_user_id for t in threads})
    out = []
    for t in threads:
        item = ThreadPublic.model_validate(t)
        item.author_name = names.get(t.created_by_user_id) if t.created_by_user_id else None
        out.append(item)
    return out


@router.post(_PREFIX, response_model=ThreadPublic, status_code=status.HTTP_201_CREATED)
async def create_thread(
    course_id: uuid.UUID,
    payload: ThreadCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.internship_id is not None and not await _may_reach_internship(db, user, organization_id, course_id, payload.internship_id):
        raise NotFoundError("Internship", payload.internship_id)
    await _may_participate(db, user, organization_id, course_id, payload.internship_id)
    service = DiscussionService(db)
    thread = await service.create_thread(course_id, organization_id, user.id, **payload.model_dump())
    return (await _out_threads(service, [thread]))[0]


@router.get(_PREFIX, response_model=list[ThreadPublic])
async def list_threads(
    course_id: uuid.UUID,
    internship_id: uuid.UUID | None = Query(default=None, description="One internship's private threads (and, with include_course, the course-wide ones)"),
    include_course: bool = False,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = DiscussionService(db)
    student = await StudentRepository(db).get_by_user_id(user.id)
    can_participate = await has_permission(db, user, PARTICIPATE)
    if student is not None and not await has_permission(db, user, MODERATE):
        await _may_participate(db, user, organization_id, course_id, None)
        threads = await service.list_threads(course_id, organization_id, internship_ids=await student_internship_ids(db, student, course_id))
    else:
        if internship_id is not None and not await _may_reach_internship(db, user, organization_id, course_id, internship_id):
            raise NotFoundError("Internship", internship_id)
        if internship_id is None:
            await _may_participate(db, user, organization_id, course_id, None)  # the course-wide list needs the course permission
        threads = await service.list_threads(course_id, organization_id, internship_id=internship_id, include_course=include_course and can_participate)
    return await _out_threads(service, threads)


@router.post(_PREFIX + "/{thread_id}/replies", response_model=ReplyPublic, status_code=status.HTTP_201_CREATED)
async def create_reply(
    course_id: uuid.UUID,
    thread_id: uuid.UUID,
    payload: ReplyCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = DiscussionService(db)
    thread = await _reachable_thread(db, user, organization_id, course_id, thread_id)
    await _may_participate(db, user, organization_id, course_id, thread.internship_id)
    reply = await service.reply(thread, user.id, payload.body)
    item = ReplyPublic.model_validate(reply)
    item.author_name = (await service.author_names({user.id})).get(user.id)
    return item


@router.get(_PREFIX + "/{thread_id}/replies", response_model=list[ReplyPublic])
async def list_replies(
    course_id: uuid.UUID,
    thread_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = DiscussionService(db)
    thread = await _reachable_thread(db, user, organization_id, course_id, thread_id)
    await _may_participate(db, user, organization_id, course_id, thread.internship_id)
    replies = await service.list_replies(thread)
    names = await service.author_names({r.created_by_user_id for r in replies})
    out = []
    for r in replies:
        item = ReplyPublic.model_validate(r)
        item.author_name = names.get(r.created_by_user_id) if r.created_by_user_id else None
        out.append(item)
    return out


@router.put(_PREFIX + "/{thread_id}/lock", response_model=ThreadPublic)
async def lock_thread(
    course_id: uuid.UUID,
    thread_id: uuid.UUID,
    payload: LockRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Lock or unlock a thread: the course permission for a course-wide thread, Our Internships manage access for an internship's own."""
    service = DiscussionService(db)
    thread = await service.get_thread(thread_id, course_id, organization_id)
    if thread.internship_id is not None:
        try:
            await authorize_internship(db, user, organization_id, thread.internship_id, "manage", course_id=course_id)
        except (AuthorizationError, NotFoundError):
            raise NotFoundError("Discussion thread", thread_id)
    elif not await has_permission(db, user, MODERATE):
        raise AuthorizationError(f"This action requires the following permission(s): {MODERATE}")
    await service.set_locked(thread, payload.is_locked)
    return (await _out_threads(service, [thread]))[0]
