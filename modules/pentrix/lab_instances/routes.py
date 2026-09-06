import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.common.dependencies import assert_can_access_student, enforce_own_student_or_staff
from modules.pentrix.lab_instances.schemas import LabInstancePublic, LaunchLabRequest
from modules.pentrix.lab_instances.service import LabInstanceService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/labs/{lab_id}/launch", response_model=LabInstancePublic, status_code=status.HTTP_201_CREATED)
async def launch_lab(
    lab_id: uuid.UUID,
    payload: LaunchLabRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.instances.launch")),
    db: AsyncSession = Depends(get_db),
):
    # `student_id` here is body-supplied, not a path param, so it can't go
    # through the `enforce_own_student_or_staff` Depends() — check it
    # explicitly before launching anything on the caller's behalf.
    await assert_can_access_student(payload.student_id, user, db)
    service = LabInstanceService(db)
    instance = await service.launch(lab_id, organization_id, payload.student_id)
    return LabInstancePublic.model_validate(instance)


@router.get("/instances/{instance_id}", response_model=LabInstancePublic)
async def get_instance(
    instance_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.instances.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LabInstanceService(db)
    instance = await service.get_instance(instance_id, organization_id)
    # `instance_id` doesn't reveal whose instance it is until fetched, so the
    # ownership check has to happen after the lookup, on the resolved
    # `student_id`, rather than as a path-param Depends().
    await assert_can_access_student(instance.student_id, user, db)
    return LabInstancePublic.model_validate(instance)


@router.get("/students/{student_id}/instances", response_model=list[LabInstancePublic])
async def list_instances_for_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.instances.view")),
    _ownership: None = Depends(enforce_own_student_or_staff),
    db: AsyncSession = Depends(get_db),
):
    service = LabInstanceService(db)
    instances = await service.list_for_student(student_id, organization_id)
    return [LabInstancePublic.model_validate(i) for i in instances]


@router.post("/instances/{instance_id}/stop", response_model=LabInstancePublic)
async def stop_instance(
    instance_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.instances.launch")),
    db: AsyncSession = Depends(get_db),
):
    service = LabInstanceService(db)
    # Ownership must be checked *before* mutating — fetch first, assert,
    # then perform the actual stop (which re-fetches internally; a small
    # extra read, but keeps this additive rather than reworking `stop()`).
    existing = await service.get_instance(instance_id, organization_id)
    await assert_can_access_student(existing.student_id, user, db)
    instance = await service.stop(instance_id, organization_id)
    return LabInstancePublic.model_validate(instance)
