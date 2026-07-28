import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.employees.models import Employee
from modules.trainers.models import Trainer


class TrainerRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Trainer:
        trainer = Trainer(**fields)
        self.db.add(trainer)
        await self.db.flush()
        await self.db.refresh(trainer)
        return trainer

    async def get_by_id(self, trainer_id: uuid.UUID, organization_id: uuid.UUID) -> Trainer | None:
        result = await self.db.execute(
            select(Trainer).where(
                Trainer.id == trainer_id, Trainer.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_employee_id(
        self, employee_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Trainer | None:
        result = await self.db.execute(
            select(Trainer).where(
                Trainer.employee_id == employee_id, Trainer.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_with_employee_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[tuple[Trainer, Employee]], int]:
        from sqlalchemy import func

        count_result = await self.db.execute(
            select(func.count()).select_from(Trainer).where(Trainer.organization_id == organization_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Trainer, Employee)
            .join(Employee, Employee.id == Trainer.employee_id)
            .where(Trainer.organization_id == organization_id)
            .order_by(Employee.full_name)
            .offset(skip)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()], total

    async def update(self, trainer: Trainer, **fields) -> Trainer:
        for key, value in fields.items():
            if value is not None:
                setattr(trainer, key, value)
        await self.db.flush()
        await self.db.refresh(trainer)
        return trainer

    async def delete(self, trainer: Trainer) -> None:
        await self.db.delete(trainer)
        await self.db.flush()
