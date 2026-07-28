import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.corporate.projects.models import Project, ProjectStatus, ProjectType


class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Project:
        project = Project(**fields)
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def get_by_id(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> Project | None:
        result = await self.db.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, project_code: str) -> Project | None:
        result = await self.db.execute(
            select(Project).where(
                Project.organization_id == organization_id, Project.project_code == project_code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        project_type: ProjectType | None = None,
        status: ProjectStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Project], int]:
        conditions = [Project.organization_id == organization_id]
        if client_id is not None:
            conditions.append(Project.client_id == client_id)
        if project_type is not None:
            conditions.append(Project.project_type == project_type)
        if status is not None:
            conditions.append(Project.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(Project).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Project).where(*conditions).order_by(Project.start_date.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, project: Project, **fields) -> Project:
        for key, value in fields.items():
            if value is not None:
                setattr(project, key, value)
        await self.db.flush()
        await self.db.refresh(project)
        return project
