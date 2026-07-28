import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.classrooms.models import Classroom
from modules.classrooms.repository import ClassroomRepository

logger = get_logger(__name__)


class ClassroomService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ClassroomRepository(db)

    async def create_classroom(self, organization_id: uuid.UUID, code: str, **fields) -> Classroom:
        existing = await self.repo.get_by_org_and_code(organization_id, code)
        if existing:
            raise ConflictError(f"A classroom with code '{code}' already exists for this organization.")
        classroom = await self.repo.create(organization_id=organization_id, code=code, **fields)
        logger.info("classroom_created", classroom_id=str(classroom.id))
        return classroom

    async def get_classroom(self, classroom_id: uuid.UUID, organization_id: uuid.UUID) -> Classroom:
        classroom = await self.repo.get_by_id(classroom_id, organization_id)
        if not classroom:
            raise NotFoundError("Classroom", classroom_id)
        return classroom

    async def list_classrooms(self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50):
        return await self.repo.list_for_organization(organization_id, skip, limit)

    async def update_classroom(
        self, classroom_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Classroom:
        classroom = await self.get_classroom(classroom_id, organization_id)
        updated = await self.repo.update(classroom, **fields)
        logger.info("classroom_updated", classroom_id=str(classroom_id))
        return updated

    async def delete_classroom(self, classroom_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        classroom = await self.get_classroom(classroom_id, organization_id)
        await self.repo.delete(classroom)
        logger.info("classroom_deleted", classroom_id=str(classroom_id))
