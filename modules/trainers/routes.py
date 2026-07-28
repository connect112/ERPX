import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.employees.repository import EmployeeRepository
from modules.trainers.dependencies import get_current_trainer
from modules.trainers.models import Trainer
from modules.trainers.schemas import (
    MessageResponse,
    TrainerCreateRequest,
    TrainerListResponse,
    TrainerPublic,
    TrainerUpdateRequest,
)
from modules.trainers.service import TrainerService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


def _to_public(trainer, employee) -> TrainerPublic:
    return TrainerPublic(
        id=trainer.id,
        organization_id=trainer.organization_id,
        employee_id=trainer.employee_id,
        employee_name=employee.full_name,
        employee_email=employee.email,
        specializations=trainer.specializations,
        bio=trainer.bio,
        max_weekly_hours=trainer.max_weekly_hours,
        is_active=trainer.is_active,
        created_at=trainer.created_at,
    )


@router.get("/me", response_model=TrainerPublic)
async def get_my_trainer_profile(
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    employee = await EmployeeRepository(db).get_by_id(trainer.employee_id, trainer.organization_id)
    return _to_public(trainer, employee)


@router.post("", response_model=TrainerPublic, status_code=status.HTTP_201_CREATED)
async def create_trainer(
    payload: TrainerCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("trainers.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TrainerService(db)
    trainer = await service.create_trainer(organization_id, **payload.model_dump())
    employee = await service.employee_repo.get_by_id(trainer.employee_id, organization_id)
    return _to_public(trainer, employee)


@router.get("", response_model=TrainerListResponse)
async def list_trainers(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("trainers.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TrainerService(db)
    rows, total = await service.list_trainers(organization_id, skip, limit)
    return TrainerListResponse(items=[_to_public(t, e) for t, e in rows], total=total)


@router.get("/{trainer_id}", response_model=TrainerPublic)
async def get_trainer(
    trainer_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("trainers.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TrainerService(db)
    trainer = await service.get_trainer(trainer_id, organization_id)
    employee = await service.employee_repo.get_by_id(trainer.employee_id, organization_id)
    return _to_public(trainer, employee)


@router.patch("/{trainer_id}", response_model=TrainerPublic)
async def update_trainer(
    trainer_id: uuid.UUID,
    payload: TrainerUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("trainers.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TrainerService(db)
    trainer = await service.update_trainer(
        trainer_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    employee = await service.employee_repo.get_by_id(trainer.employee_id, organization_id)
    return _to_public(trainer, employee)


@router.delete("/{trainer_id}", response_model=MessageResponse)
async def delete_trainer(
    trainer_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("trainers.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TrainerService(db)
    await service.delete_trainer(trainer_id, organization_id)
    return MessageResponse(message="Trainer deleted successfully.")
