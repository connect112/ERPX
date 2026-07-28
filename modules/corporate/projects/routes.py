import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.corporate.projects.models import ProjectStatus, ProjectType
from modules.corporate.projects.schemas import (
    MessageResponse,
    ProjectCreateRequest,
    ProjectPublic,
    ProjectStatusChangeRequest,
    ProjectUpdateRequest,
)
from modules.corporate.clients.dependencies import get_current_client
from modules.corporate.clients.models import Client
from modules.corporate.projects.service import ProjectService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=list[ProjectPublic])
async def list_my_projects(
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    projects, _total = await service.list_projects(
        client.organization_id, client_id=client.id, skip=0, limit=200
    )
    return [ProjectPublic.model_validate(p) for p in projects]


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.projects.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.create_project(organization_id, **payload.model_dump())
    return ProjectPublic.model_validate(project)


@router.get("", response_model=dict)
async def list_projects(
    client_id: uuid.UUID | None = None,
    project_type: ProjectType | None = None,
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.projects.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    projects, total = await service.list_projects(
        organization_id, client_id=client_id, project_type=project_type, status=status_filter, skip=skip, limit=limit
    )
    return {
        "items": [ProjectPublic.model_validate(p) for p in projects],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{project_id}", response_model=ProjectPublic)
async def get_project(
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.projects.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get_project(project_id, organization_id)
    return ProjectPublic.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectPublic)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.projects.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.update_project(project_id, organization_id, **payload.model_dump(exclude_unset=True))
    return ProjectPublic.model_validate(project)


@router.post("/{project_id}/status", response_model=ProjectPublic)
async def change_project_status(
    project_id: uuid.UUID,
    payload: ProjectStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("corporate.projects.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.change_status(project_id, organization_id, payload.status)
    return ProjectPublic.model_validate(project)
