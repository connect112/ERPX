import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.hr.models import Department, Designation


class DepartmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Department:
        department = Department(**fields)
        self.db.add(department)
        await self.db.flush()
        await self.db.refresh(department)
        return department

    async def get_by_id(self, department_id: uuid.UUID, organization_id: uuid.UUID) -> Department | None:
        result = await self.db.execute(
            select(Department).where(
                Department.id == department_id, Department.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> Department | None:
        result = await self.db.execute(
            select(Department).where(Department.organization_id == organization_id, Department.code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[Department]:
        conditions = [Department.organization_id == organization_id]
        if is_active is not None:
            conditions.append(Department.is_active == is_active)
        result = await self.db.execute(select(Department).where(*conditions).order_by(Department.name.asc()))
        return list(result.scalars().all())

    async def update(self, department: Department, **fields) -> Department:
        for key, value in fields.items():
            if value is not None:
                setattr(department, key, value)
        await self.db.flush()
        await self.db.refresh(department)
        return department


class DesignationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Designation:
        designation = Designation(**fields)
        self.db.add(designation)
        await self.db.flush()
        await self.db.refresh(designation)
        return designation

    async def get_by_id(self, designation_id: uuid.UUID, organization_id: uuid.UUID) -> Designation | None:
        result = await self.db.execute(
            select(Designation).where(
                Designation.id == designation_id, Designation.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> Designation | None:
        result = await self.db.execute(
            select(Designation).where(
                Designation.organization_id == organization_id, Designation.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[Designation]:
        conditions = [Designation.organization_id == organization_id]
        if is_active is not None:
            conditions.append(Designation.is_active == is_active)
        result = await self.db.execute(select(Designation).where(*conditions).order_by(Designation.title.asc()))
        return list(result.scalars().all())

    async def update(self, designation: Designation, **fields) -> Designation:
        for key, value in fields.items():
            if value is not None:
                setattr(designation, key, value)
        await self.db.flush()
        await self.db.refresh(designation)
        return designation
