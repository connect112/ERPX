import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging_config import get_logger
from modules.employees.repository import EmployeeRepository
from modules.trainers.models import Trainer
from modules.trainers.repository import TrainerRepository

logger = get_logger(__name__)


class TrainerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TrainerRepository(db)
        self.employee_repo = EmployeeRepository(db)

    async def create_trainer(self, organization_id: uuid.UUID, employee_id: uuid.UUID, **fields) -> Trainer:
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)

        existing = await self.repo.get_by_employee_id(employee_id, organization_id)
        if existing:
            raise ConflictError("This employee already has a trainer profile.")

        trainer = await self.repo.create(organization_id=organization_id, employee_id=employee_id, **fields)
        logger.info("trainer_created", trainer_id=str(trainer.id), employee_id=str(employee_id))
        return trainer

    async def get_trainer(self, trainer_id: uuid.UUID, organization_id: uuid.UUID) -> Trainer:
        trainer = await self.repo.get_by_id(trainer_id, organization_id)
        if not trainer:
            raise NotFoundError("Trainer", trainer_id)
        return trainer

    async def list_trainers(self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50):
        return await self.repo.list_with_employee_for_organization(organization_id, skip, limit)

    async def update_trainer(self, trainer_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Trainer:
        trainer = await self.get_trainer(trainer_id, organization_id)
        updated = await self.repo.update(trainer, **fields)
        logger.info("trainer_updated", trainer_id=str(trainer_id))
        return updated

    async def delete_trainer(self, trainer_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        trainer = await self.get_trainer(trainer_id, organization_id)
        await self.repo.delete(trainer)
        logger.info("trainer_deleted", trainer_id=str(trainer_id))
