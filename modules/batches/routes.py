import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.batches.models import BatchStatus
from modules.batches.schemas import (
    BatchCreateRequest,
    BatchListResponse,
    BatchPublic,
    BatchUpdateRequest,
    BatchWithCoursePublic,
    MessageResponse,
)
from modules.batches.repository import BatchRepository
from modules.batches.service import BatchService
from modules.courses.repository import CourseRepository
from modules.trainers.dependencies import get_current_trainer
from modules.trainers.models import Trainer
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=list[BatchWithCoursePublic])
async def list_my_batches(
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    batches = await BatchRepository(db).list_for_trainer(trainer.id, trainer.organization_id)
    course_repo = CourseRepository(db)
    course_titles: dict = {}
    results = []
    for batch in batches:
        if batch.course_id not in course_titles:
            course = await course_repo.get_by_id(batch.course_id, trainer.organization_id)
            course_titles[batch.course_id] = course.title if course else "Unknown course"
        results.append(
            BatchWithCoursePublic(
                **BatchPublic.model_validate(batch).model_dump(),
                course_title=course_titles[batch.course_id],
            )
        )
    return results


@router.post("", response_model=BatchPublic, status_code=status.HTTP_201_CREATED)
async def create_batch(
    payload: BatchCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("batches.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BatchService(db)
    batch = await service.create_batch(organization_id, **payload.model_dump())
    return BatchPublic.model_validate(batch)


@router.get("", response_model=BatchListResponse)
async def list_batches(
    course_id: uuid.UUID | None = None,
    status_filter: BatchStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("batches.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BatchService(db)
    items, total = await service.list_batches(
        organization_id, course_id=course_id, status=status_filter, skip=skip, limit=limit
    )
    return BatchListResponse(items=[BatchPublic.model_validate(b) for b in items], total=total)


@router.get("/{batch_id}", response_model=BatchPublic)
async def get_batch(
    batch_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("batches.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BatchService(db)
    batch = await service.get_batch(batch_id, organization_id)
    return BatchPublic.model_validate(batch)


@router.patch("/{batch_id}", response_model=BatchPublic)
async def update_batch(
    batch_id: uuid.UUID,
    payload: BatchUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("batches.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BatchService(db)
    batch = await service.update_batch(
        batch_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return BatchPublic.model_validate(batch)


@router.delete("/{batch_id}", response_model=MessageResponse)
async def delete_batch(
    batch_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("batches.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BatchService(db)
    await service.delete_batch(batch_id, organization_id)
    return MessageResponse(message="Batch deleted successfully.")
