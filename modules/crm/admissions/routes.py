import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.crm.admissions.schemas import (
    AdmissionCreateRequest,
    AdmissionPublic,
    AdmissionUpdateRequest,
)
from modules.crm.admissions.service import AdmissionService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post(
    "/leads/{lead_id}/admission", response_model=AdmissionPublic, status_code=status.HTTP_201_CREATED
)
async def create_admission(
    lead_id: uuid.UUID,
    payload: AdmissionCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.admissions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AdmissionService(db)
    admission = await service.create_admission(
        lead_id, organization_id, created_by_user_id=user.id, **payload.model_dump()
    )
    return AdmissionPublic.model_validate(admission)


@router.get("/admissions", response_model=list[AdmissionPublic])
async def list_admissions(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.admissions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AdmissionService(db)
    admissions = await service.list_admissions(organization_id)
    return [AdmissionPublic.model_validate(a) for a in admissions]


@router.get("/leads/{lead_id}/admission", response_model=AdmissionPublic)
async def get_admission_for_lead(
    lead_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.admissions.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AdmissionService(db)
    admission = await service.get_admission_for_lead(lead_id, organization_id)
    return AdmissionPublic.model_validate(admission)


@router.patch("/admissions/{admission_id}", response_model=AdmissionPublic)
async def update_admission(
    admission_id: uuid.UUID,
    payload: AdmissionUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.admissions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AdmissionService(db)
    admission = await service.update_admission(
        admission_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AdmissionPublic.model_validate(admission)


@router.post("/admissions/{admission_id}/cancel", response_model=AdmissionPublic)
async def cancel_admission(
    admission_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("crm.admissions.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AdmissionService(db)
    admission = await service.cancel_admission(admission_id, organization_id)
    return AdmissionPublic.model_validate(admission)
