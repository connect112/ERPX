import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.examinations.viva.schemas import (
    MessageResponse,
    RecordVivaResultRequest,
    VivaCreateRequest,
    VivaPublic,
    VivaResultPublic,
    VivaUpdateRequest,
)
from modules.examinations.viva.service import VivaService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/viva"


@router.post(_PREFIX, response_model=VivaPublic, status_code=status.HTTP_201_CREATED)
async def create_viva(
    course_id: uuid.UUID,
    payload: VivaCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.viva.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.create_viva(course_id, organization_id, **payload.model_dump())
    return VivaPublic.model_validate(viva)


@router.get(_PREFIX, response_model=list[VivaPublic])
async def list_vivas(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.viva.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    vivas = await service.list_vivas(course_id, organization_id)
    return [VivaPublic.model_validate(v) for v in vivas]


@router.get(_PREFIX + "/{viva_id}", response_model=VivaPublic)
async def get_viva(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.viva.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.get_viva(viva_id, course_id, organization_id)
    return VivaPublic.model_validate(viva)


@router.patch(_PREFIX + "/{viva_id}", response_model=VivaPublic)
async def update_viva(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    payload: VivaUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.viva.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    viva = await service.update_viva(
        viva_id, course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return VivaPublic.model_validate(viva)


@router.delete(_PREFIX + "/{viva_id}", response_model=MessageResponse)
async def delete_viva(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.viva.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    await service.delete_viva(viva_id, course_id, organization_id)
    return MessageResponse(message="Viva exam deleted successfully.")


@router.post(_PREFIX + "/{viva_id}/results", response_model=VivaResultPublic, status_code=status.HTTP_201_CREATED)
async def record_result(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    payload: RecordVivaResultRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.viva.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    result_row = await service.record_result(
        viva_id, course_id, organization_id, payload.student_id, payload.score, payload.remarks, user.id
    )
    return VivaResultPublic.model_validate(result_row)


@router.get(_PREFIX + "/{viva_id}/results", response_model=list[VivaResultPublic])
async def list_results(
    course_id: uuid.UUID,
    viva_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.viva.view")),
    db: AsyncSession = Depends(get_db),
):
    service = VivaService(db)
    results = await service.list_results(viva_id, course_id, organization_id)
    return [VivaResultPublic.model_validate(r) for r in results]
