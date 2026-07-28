import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.labs.schemas import LabCreateRequest, LabPublic, LabUpdateRequest, MessageResponse
from modules.pentrix.labs.service import LabService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=LabPublic, status_code=status.HTTP_201_CREATED)
async def create_lab(
    payload: LabCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.labs.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LabService(db)
    lab = await service.create_lab(organization_id, **payload.model_dump())
    return LabPublic.model_validate(lab)


@router.get("", response_model=list[LabPublic])
async def list_labs(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.labs.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LabService(db)
    labs = await service.list_labs(organization_id)
    return [LabPublic.model_validate(l) for l in labs]


@router.get("/{lab_id}", response_model=LabPublic)
async def get_lab(
    lab_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.labs.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LabService(db)
    lab = await service.get_lab(lab_id, organization_id)
    return LabPublic.model_validate(lab)


@router.patch("/{lab_id}", response_model=LabPublic)
async def update_lab(
    lab_id: uuid.UUID,
    payload: LabUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.labs.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LabService(db)
    lab = await service.update_lab(lab_id, organization_id, **payload.model_dump(exclude_unset=True))
    return LabPublic.model_validate(lab)


@router.delete("/{lab_id}", response_model=MessageResponse)
async def delete_lab(
    lab_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.labs.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LabService(db)
    await service.delete_lab(lab_id, organization_id)
    return MessageResponse(message="Lab deleted successfully.")
