import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.classrooms.models import Classroom


class ClassroomRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Classroom:
        classroom = Classroom(**fields)
        self.db.add(classroom)
        await self.db.flush()
        await self.db.refresh(classroom)
        return classroom

    async def get_by_id(self, classroom_id: uuid.UUID, organization_id: uuid.UUID) -> Classroom | None:
        result = await self.db.execute(
            select(Classroom).where(
                Classroom.id == classroom_id, Classroom.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_org_and_code(self, organization_id: uuid.UUID, code: str) -> Classroom | None:
        result = await self.db.execute(
            select(Classroom).where(
                Classroom.organization_id == organization_id, Classroom.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Classroom], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(Classroom).where(Classroom.organization_id == organization_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Classroom)
            .where(Classroom.organization_id == organization_id)
            .order_by(Classroom.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, classroom: Classroom, **fields) -> Classroom:
        for key, value in fields.items():
            if value is not None:
                setattr(classroom, key, value)
        await self.db.flush()
        await self.db.refresh(classroom)
        return classroom

    async def delete(self, classroom: Classroom) -> None:
        await self.db.delete(classroom)
        await self.db.flush()
