import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.examinations.practicals.schemas import (
    MessageResponse,
    PracticalCreateRequest,
    PracticalPublic,
    PracticalResultPublic,
    PracticalUpdateRequest,
    RecordPracticalResultRequest,
)
from modules.examinations.practicals.service import PracticalService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/practicals"


@router.post(_PREFIX, response_model=PracticalPublic, status_code=status.HTTP_201_CREATED)
async def create_practical(
    course_id: uuid.UUID,
    payload: PracticalCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.practicals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.create_practical(course_id, organization_id, **payload.model_dump())
    return PracticalPublic.model_validate(practical)


@router.get(_PREFIX, response_model=list[PracticalPublic])
async def list_practicals(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.practicals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practicals = await service.list_practicals(course_id, organization_id)
    return [PracticalPublic.model_validate(p) for p in practicals]


@router.get(_PREFIX + "/{practical_id}", response_model=PracticalPublic)
async def get_practical(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.practicals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.get_practical(practical_id, course_id, organization_id)
    return PracticalPublic.model_validate(practical)


@router.patch(_PREFIX + "/{practical_id}", response_model=PracticalPublic)
async def update_practical(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    payload: PracticalUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.practicals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    practical = await service.update_practical(
        practical_id, course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return PracticalPublic.model_validate(practical)


@router.delete(_PREFIX + "/{practical_id}", response_model=MessageResponse)
async def delete_practical(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.practicals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    await service.delete_practical(practical_id, course_id, organization_id)
    return MessageResponse(message="Practical exam deleted successfully.")


@router.post(_PREFIX + "/{practical_id}/results", response_model=PracticalResultPublic, status_code=status.HTTP_201_CREATED)
async def record_result(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    payload: RecordPracticalResultRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.practicals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    result_row = await service.record_result(
        practical_id, course_id, organization_id, payload.student_id, payload.score, payload.remarks, user.id
    )
    return PracticalResultPublic.model_validate(result_row)


@router.get(_PREFIX + "/{practical_id}/results", response_model=list[PracticalResultPublic])
async def list_results(
    course_id: uuid.UUID,
    practical_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.practicals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PracticalService(db)
    results = await service.list_results(practical_id, course_id, organization_id)
    return [PracticalResultPublic.model_validate(r) for r in results]
