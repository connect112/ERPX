import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.payroll.models import (
    Payslip,
    PayslipLine,
    PayrollRun,
    PayrollRunStatus,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureLine,
)


class SalaryComponentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> SalaryComponent:
        component = SalaryComponent(**fields)
        self.db.add(component)
        await self.db.flush()
        await self.db.refresh(component)
        return component

    async def get_by_id(self, component_id: uuid.UUID, organization_id: uuid.UUID) -> SalaryComponent | None:
        result = await self.db.execute(
            select(SalaryComponent).where(
                SalaryComponent.id == component_id, SalaryComponent.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> SalaryComponent | None:
        result = await self.db.execute(
            select(SalaryComponent).where(
                SalaryComponent.organization_id == organization_id, SalaryComponent.code == code
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, is_active: bool | None = None
    ) -> list[SalaryComponent]:
        conditions = [SalaryComponent.organization_id == organization_id]
        if is_active is not None:
            conditions.append(SalaryComponent.is_active == is_active)
        result = await self.db.execute(
            select(SalaryComponent).where(*conditions).order_by(SalaryComponent.name.asc())
        )
        return list(result.scalars().all())

    async def update(self, component: SalaryComponent, **fields) -> SalaryComponent:
        for key, value in fields.items():
            if value is not None:
                setattr(component, key, value)
        await self.db.flush()
        await self.db.refresh(component)
        return component


class SalaryStructureRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lines: list[dict], **fields) -> SalaryStructure:
        structure = SalaryStructure(**fields)
        self.db.add(structure)
        await self.db.flush()
        for line in lines:
            self.db.add(SalaryStructureLine(salary_structure_id=structure.id, **line))
        await self.db.flush()
        return await self.get_by_id(structure.id, structure.organization_id)

    async def get_by_id(self, structure_id: uuid.UUID, organization_id: uuid.UUID) -> SalaryStructure | None:
        result = await self.db.execute(
            select(SalaryStructure)
            .where(SalaryStructure.id == structure_id, SalaryStructure.organization_id == organization_id)
            .options(selectinload(SalaryStructure.lines))
        )
        return result.scalar_one_or_none()

    async def get_active_for_employee(
        self, employee_id: uuid.UUID, as_of_date: date
    ) -> SalaryStructure | None:
        result = await self.db.execute(
            select(SalaryStructure)
            .where(
                SalaryStructure.employee_id == employee_id,
                SalaryStructure.effective_from <= as_of_date,
                (SalaryStructure.effective_to.is_(None)) | (SalaryStructure.effective_to >= as_of_date),
            )
            .options(selectinload(SalaryStructure.lines))
            .order_by(SalaryStructure.effective_from.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_current_active(self, employee_id: uuid.UUID) -> SalaryStructure | None:
        result = await self.db.execute(
            select(SalaryStructure).where(
                SalaryStructure.employee_id == employee_id, SalaryStructure.is_active.is_(True)
            )
        )
        return result.scalar_one_or_none()

    async def list_for_employee(self, employee_id: uuid.UUID) -> list[SalaryStructure]:
        result = await self.db.execute(
            select(SalaryStructure)
            .where(SalaryStructure.employee_id == employee_id)
            .options(selectinload(SalaryStructure.lines))
            .order_by(SalaryStructure.effective_from.desc())
        )
        return list(result.scalars().all())

    async def close_structure(self, structure: SalaryStructure, effective_to: date) -> None:
        structure.effective_to = effective_to
        structure.is_active = False
        await self.db.flush()


class PayrollRunRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> PayrollRun:
        run = PayrollRun(**fields)
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def get_by_id(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> PayrollRun | None:
        result = await self.db.execute(
            select(PayrollRun).where(PayrollRun.id == run_id, PayrollRun.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_for_period(
        self, organization_id: uuid.UUID, period_year: int, period_month: int, branch_id: uuid.UUID | None
    ) -> PayrollRun | None:
        result = await self.db.execute(
            select(PayrollRun).where(
                PayrollRun.organization_id == organization_id,
                PayrollRun.period_year == period_year,
                PayrollRun.period_month == period_month,
                PayrollRun.branch_id == branch_id if branch_id is not None else PayrollRun.branch_id.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: PayrollRunStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[PayrollRun], int]:
        conditions = [PayrollRun.organization_id == organization_id]
        if status is not None:
            conditions.append(PayrollRun.status == status)

        count_result = await self.db.execute(select(func.count()).select_from(PayrollRun).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(PayrollRun)
            .where(*conditions)
            .order_by(PayrollRun.period_year.desc(), PayrollRun.period_month.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, run: PayrollRun, **fields) -> PayrollRun:
        for key, value in fields.items():
            if value is not None:
                setattr(run, key, value)
        await self.db.flush()
        await self.db.refresh(run)
        return run


class PayslipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lines: list[dict], **fields) -> Payslip:
        payslip = Payslip(**fields)
        self.db.add(payslip)
        await self.db.flush()
        for line in lines:
            self.db.add(PayslipLine(payslip_id=payslip.id, **line))
        await self.db.flush()
        return await self.get_by_id(payslip.id)

    async def get_by_id(self, payslip_id: uuid.UUID) -> Payslip | None:
        result = await self.db.execute(
            select(Payslip).where(Payslip.id == payslip_id).options(selectinload(Payslip.lines))
        )
        return result.scalar_one_or_none()

    async def list_for_run(self, payroll_run_id: uuid.UUID) -> list[Payslip]:
        result = await self.db.execute(
            select(Payslip)
            .where(Payslip.payroll_run_id == payroll_run_id)
            .options(selectinload(Payslip.lines))
            .order_by(Payslip.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_employee(self, employee_id: uuid.UUID, skip: int = 0, limit: int = 50) -> tuple[list[Payslip], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(Payslip).where(Payslip.employee_id == employee_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Payslip)
            .where(Payslip.employee_id == employee_id)
            .options(selectinload(Payslip.lines))
            .order_by(Payslip.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total
