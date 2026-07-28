import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.soc.models import IncidentStatus, SOCServiceStatus
from modules.corporate.soc.schemas import (
    MessageResponse,
    SOCIncidentCreateRequest,
    SOCIncidentPublic,
    SOCIncidentUpdateRequest,
    SOCServiceCreateRequest,
    SOCServicePublic,
    SOCServiceUpdateRequest,
)
from modules.corporate.soc.service import SOCIncidentService, SOCServiceService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/services", response_model=SOCServicePublic, status_code=status.HTTP_201_CREATED)
async def create_soc_service(
    payload: SOCServiceCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.soc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SOCServiceService(db)
    soc_service = await service.create_service(organization_id, **payload.model_dump())
    return SOCServicePublic.model_validate(soc_service)


@router.get("/services/clients/{client_id}", response_model=list[SOCServicePublic])
async def list_soc_services_for_client(
    client_id: uuid.UUID,
    status_filter: SOCServiceStatus | None = Query(default=None, alias="status"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.soc.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SOCServiceService(db)
    services = await service.list_for_client(client_id, organization_id, status=status_filter)
    return [SOCServicePublic.model_validate(s) for s in services]


@router.get("/services/{soc_service_id}", response_model=SOCServicePublic)
async def get_soc_service(
    soc_service_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.soc.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SOCServiceService(db)
    soc_service = await service.get_service(soc_service_id, organization_id)
    return SOCServicePublic.model_validate(soc_service)


@router.patch("/services/{soc_service_id}", response_model=SOCServicePublic)
async def update_soc_service(
    soc_service_id: uuid.UUID,
    payload: SOCServiceUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.soc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SOCServiceService(db)
    soc_service = await service.update_service(
        soc_service_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return SOCServicePublic.model_validate(soc_service)


@router.post(
    "/services/{soc_service_id}/incidents", response_model=SOCIncidentPublic, status_code=status.HTTP_201_CREATED
)
async def create_incident(
    soc_service_id: uuid.UUID,
    payload: SOCIncidentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.soc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SOCIncidentService(db)
    incident = await service.create_incident(soc_service_id, organization_id, **payload.model_dump())
    return SOCIncidentPublic.model_validate(incident)


@router.get("/services/{soc_service_id}/incidents", response_model=list[SOCIncidentPublic])
async def list_incidents(
    soc_service_id: uuid.UUID,
    status_filter: IncidentStatus | None = Query(default=None, alias="status"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.soc.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SOCIncidentService(db)
    incidents = await service.list_incidents(soc_service_id, organization_id, status_filter)
    return [SOCIncidentPublic.model_validate(i) for i in incidents]


@router.patch("/incidents/{incident_id}", response_model=SOCIncidentPublic)
async def update_incident(
    incident_id: uuid.UUID,
    payload: SOCIncidentUpdateRequest,
    user: User = Depends(require_permissions("corporate.soc.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SOCIncidentService(db)
    incident = await service.update_incident(incident_id, **payload.model_dump(exclude_unset=True))
    return SOCIncidentPublic.model_validate(incident)
