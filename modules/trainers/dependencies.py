"""
Trainers module — FastAPI dependencies.

`get_current_trainer` is what every self-service "me" endpoint (trainer
portal: my batches, grading, attendance, ...) depends on instead of an
RBAC permission check — a trainer doesn't need `batches.view` to see
their *own* batches; owning the record is the authorization. A trainer
account resolves through the Employee it's layered on: User -> Employee
(via Employee.user_id) -> Trainer (via Trainer.employee_id).
"""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.employees.repository import EmployeeRepository
from modules.trainers.models import Trainer
from modules.trainers.repository import TrainerRepository


async def get_current_trainer(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Trainer:
    employee = await EmployeeRepository(db).get_by_user_id(user.id)
    if not employee:
        raise ValidationError(
            "Your account is not linked to an employee record. Contact your administrator."
        )
    trainer = await TrainerRepository(db).get_by_employee_id(employee.id, employee.organization_id)
    if not trainer:
        raise ValidationError(
            "Your account is not linked to a trainer profile. Contact your administrator."
        )
    return trainer


async def get_current_trainer_organization_id(
    trainer: Trainer = Depends(get_current_trainer),
) -> uuid.UUID:
    return trainer.organization_id
