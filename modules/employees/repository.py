import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.employees.models import Employee, EmploymentStatus


class EmployeeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Employee:
        employee = Employee(**fields)
        self.db.add(employee)
        await self.db.flush()
        await self.db.refresh(employee)
        return employee

    async def get_by_id(self, employee_id: uuid.UUID, organization_id: uuid.UUID) -> Employee | None:
        result = await self.db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.organization_id == organization_id,
                Employee.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, employee_code: str) -> Employee | None:
        result = await self.db.execute(
            select(Employee).where(
                Employee.organization_id == organization_id, Employee.employee_code == employee_code
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Employee | None:
        result = await self.db.execute(
            select(Employee).where(Employee.user_id == user_id, Employee.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        designation_id: uuid.UUID | None = None,
        employment_status: EmploymentStatus | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Employee], int]:
        conditions = [Employee.organization_id == organization_id, Employee.deleted_at.is_(None)]
        if department_id is not None:
            conditions.append(Employee.department_id == department_id)
        if designation_id is not None:
            conditions.append(Employee.designation_id == designation_id)
        if employment_status is not None:
            conditions.append(Employee.employment_status == employment_status)
        if search:
            like_pattern = f"%{search}%"
            conditions.append(
                (Employee.full_name.ilike(like_pattern))
                | (Employee.employee_code.ilike(like_pattern))
                | (Employee.email.ilike(like_pattern))
            )

        count_result = await self.db.execute(select(func.count()).select_from(Employee).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Employee).where(*conditions).order_by(Employee.full_name.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_direct_reports(self, manager_id: uuid.UUID) -> list[Employee]:
        result = await self.db.execute(
            select(Employee).where(Employee.reporting_manager_id == manager_id, Employee.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def update(self, employee: Employee, **fields) -> Employee:
        for key, value in fields.items():
            if value is not None:
                setattr(employee, key, value)
        await self.db.flush()
        await self.db.refresh(employee)
        return employee

    async def soft_delete(self, employee: Employee) -> None:
        from datetime import datetime, timezone

        employee.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
