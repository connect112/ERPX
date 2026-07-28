import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.corporate.clients.repository import ClientRepository
from modules.corporate.projects.models import Project
from modules.corporate.projects.repository import ProjectRepository

logger = get_logger(__name__)


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProjectRepository(db)
        self.client_repo = ClientRepository(db)

    async def create_project(self, organization_id: uuid.UUID, client_id: uuid.UUID, project_code: str, **fields) -> Project:
        client = await self.client_repo.get_by_id(client_id, organization_id)
        if not client:
            raise NotFoundError("Client", client_id)
        existing = await self.repo.get_by_code(organization_id, project_code)
        if existing:
            raise ConflictError(f"A project with code '{project_code}' already exists.")

        project = await self.repo.create(
            organization_id=organization_id, client_id=client_id, project_code=project_code, **fields
        )
        logger.info("corporate_project_created", project_id=str(project.id))
        return project

    async def get_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> Project:
        project = await self.repo.get_by_id(project_id, organization_id)
        if not project:
            raise NotFoundError("Project", project_id)
        return project

    async def list_projects(self, organization_id: uuid.UUID, **filters) -> tuple[list[Project], int]:
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_project(self, project_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Project:
        project = await self.get_project(project_id, organization_id)
        updated = await self.repo.update(project, **fields)
        logger.info("corporate_project_updated", project_id=str(project_id))
        return updated

    async def change_status(self, project_id: uuid.UUID, organization_id: uuid.UUID, status) -> Project:
        project = await self.get_project(project_id, organization_id)
        updated = await self.repo.update(project, status=status)
        logger.info("corporate_project_status_changed", project_id=str(project_id), status=status.value)
        return updated
