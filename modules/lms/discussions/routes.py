import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.discussions.schemas import (
    ReplyCreateRequest,
    ReplyPublic,
    ThreadCreateRequest,
    ThreadPublic,
)
from modules.lms.discussions.service import DiscussionService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/discussions"


@router.post(_PREFIX, response_model=ThreadPublic, status_code=status.HTTP_201_CREATED)
async def create_thread(
    course_id: uuid.UUID,
    payload: ThreadCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.discussions.participate")),
    db: AsyncSession = Depends(get_db),
):
    service = DiscussionService(db)
    thread = await service.create_thread(course_id, organization_id, user.id, **payload.model_dump())
    return ThreadPublic.model_validate(thread)


@router.get(_PREFIX, response_model=list[ThreadPublic])
async def list_threads(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.discussions.participate")),
    db: AsyncSession = Depends(get_db),
):
    service = DiscussionService(db)
    threads = await service.list_threads(course_id, organization_id)
    return [ThreadPublic.model_validate(t) for t in threads]


@router.post(
    _PREFIX + "/{thread_id}/replies", response_model=ReplyPublic, status_code=status.HTTP_201_CREATED
)
async def create_reply(
    course_id: uuid.UUID,
    thread_id: uuid.UUID,
    payload: ReplyCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.discussions.participate")),
    db: AsyncSession = Depends(get_db),
):
    service = DiscussionService(db)
    reply = await service.reply(thread_id, course_id, organization_id, user.id, payload.body)
    return ReplyPublic.model_validate(reply)


@router.get(_PREFIX + "/{thread_id}/replies", response_model=list[ReplyPublic])
async def list_replies(
    course_id: uuid.UUID,
    thread_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.discussions.participate")),
    db: AsyncSession = Depends(get_db),
):
    service = DiscussionService(db)
    replies = await service.list_replies(thread_id, course_id, organization_id)
    return [ReplyPublic.model_validate(r) for r in replies]
