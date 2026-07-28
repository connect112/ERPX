import calendar
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.bank.models import BankTransactionSource
from modules.accounting.bank.repository import BankAccountRepository
from modules.accounting.bank.service import BankService
from modules.accounting.journals.models import JournalSourceModule
from modules.accounting.journals.service import JournalService
from modules.accounting.ledger.repository import AccountRepository
from modules.attendance.service import AttendanceService
from modules.employees.models import EmploymentStatus
from modules.employees.repository import EmployeeRepository
from modules.payroll.models import (
    Payslip,
    PayrollRun,
    PayrollRunStatus,
    SalaryComponent,
    SalaryComponentType,
    SalaryStructure,
)
from modules.payroll.repository import (
    PayrollRunRepository,
    PayslipRepository,
    SalaryComponentRepository,
    SalaryStructureRepository,
)

logger = get_logger(__name__)


class SalaryComponentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SalaryComponentRepository(db)
        self.account_repo = AccountRepository(db)

    async def create_component(self, organization_id: uuid.UUID, code: str, gl_account_id: uuid.UUID, **fields) -> SalaryComponent:
        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A salary component with code '{code}' already exists.")
        account = await self.account_repo.get_by_id(gl_account_id, organization_id)
        if not account:
            raise NotFoundError("GL account", gl_account_id)
        component = await self.repo.create(
            organization_id=organization_id, code=code, gl_account_id=gl_account_id, **fields
        )
        logger.info("salary_component_created", component_id=str(component.id))
        return component

    async def get_component(self, component_id: uuid.UUID, organization_id: uuid.UUID) -> SalaryComponent:
        component = await self.repo.get_by_id(component_id, organization_id)
        if not component:
            raise NotFoundError("Salary component", component_id)
        return component

    async def list_components(self, organization_id: uuid.UUID, is_active: bool | None = None) -> list[SalaryComponent]:
        return await self.repo.list_for_organization(organization_id, is_active)

    async def update_component(self, component_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> SalaryComponent:
        component = await self.get_component(component_id, organization_id)
        if fields.get("gl_account_id") is not None:
            account = await self.account_repo.get_by_id(fields["gl_account_id"], organization_id)
            if not account:
                raise NotFoundError("GL account", fields["gl_account_id"])
        updated = await self.repo.update(component, **fields)
        logger.info("salary_component_updated", component_id=str(component_id))
        return updated


class SalaryStructureService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SalaryStructureRepository(db)
        self.component_repo = SalaryComponentRepository(db)
        self.employee_repo = EmployeeRepository(db)

    async def create_structure(
        self,
        organization_id: uuid.UUID,
        employee_id: uuid.UUID,
        effective_from: date,
        lines: list[dict],
        notes: str | None = None,
    ) -> SalaryStructure:
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)

        gross = 0.0
        deductions = 0.0
        for line in lines:
            component = await self.component_repo.get_by_id(line["salary_component_id"], organization_id)
            if not component:
                raise NotFoundError("Salary component", line["salary_component_id"])
            if not component.is_active:
                raise ValidationError(f"Salary component '{component.name}' is not active.")
            if component.component_type == SalaryComponentType.EARNING:
                gross += float(line["amount"])
            else:
                deductions += float(line["amount"])

        if gross <= 0:
            raise ValidationError("A salary structure must include at least one earning component with a positive amount.")

        current = await self.repo.get_current_active(employee_id)
        if current is not None:
            if effective_from <= current.effective_from:
                raise ValidationError(
                    f"effective_from must be after the current structure's effective_from ({current.effective_from})."
                )
            await self.repo.close_structure(current, effective_to=effective_from - timedelta(days=1))

        structure = await self.repo.create(
            lines=lines,
            organization_id=organization_id,
            employee_id=employee_id,
            effective_from=effective_from,
            effective_to=None,
            gross_monthly_amount=round(gross, 2),
            total_deductions=round(deductions, 2),
            net_monthly_amount=round(gross - deductions, 2),
            is_active=True,
            notes=notes,
        )
        logger.info("salary_structure_created", structure_id=str(structure.id), employee_id=str(employee_id))
        return structure

    async def get_structure(self, structure_id: uuid.UUID, organization_id: uuid.UUID) -> SalaryStructure:
        structure = await self.repo.get_by_id(structure_id, organization_id)
        if not structure:
            raise NotFoundError("Salary structure", structure_id)
        return structure

    async def list_for_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID) -> list[SalaryStructure]:
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        return await self.repo.list_for_employee(employee_id)


class PayrollService:
    """
    Earnings are prorated for Loss-of-Pay days derived from Attendance
    (`paid_days` / `days_in_month`); deductions are booked at their full
    structure amount regardless of LOP — a deliberate simplification
    (real statutory deductions like PF are often computed on *earned*
    basic, not structure basic) documented here rather than silently
    assumed.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.run_repo = PayrollRunRepository(db)
        self.payslip_repo = PayslipRepository(db)
        self.structure_repo = SalaryStructureRepository(db)
        self.component_repo = SalaryComponentRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.account_repo = AccountRepository(db)
        self.bank_account_repo = BankAccountRepository(db)
        self.attendance_service = AttendanceService(db)
        self.bank_service = BankService(db)
        self.journal_service = JournalService(db)

    async def generate_run(
        self,
        organization_id: uuid.UUID,
        period_year: int,
        period_month: int,
        run_date: date,
        branch_id: uuid.UUID | None = None,
        created_by_user_id: uuid.UUID | None = None,
    ) -> tuple[PayrollRun, int, list[uuid.UUID]]:
        existing = await self.run_repo.get_for_period(organization_id, period_year, period_month, branch_id)
        if existing is not None:
            raise ConflictError(
                f"A payroll run for {period_year}-{period_month:02d} already exists for this organization/branch."
            )

        days_in_month = calendar.monthrange(period_year, period_month)[1]
        employees, _ = await self.employee_repo.list_for_organization(
            organization_id, employment_status=EmploymentStatus.ACTIVE, skip=0, limit=10_000
        )
        if branch_id is not None:
            employees = [e for e in employees if e.branch_id == branch_id]

        run = await self.run_repo.create(
            organization_id=organization_id,
            branch_id=branch_id,
            period_year=period_year,
            period_month=period_month,
            run_date=run_date,
            status=PayrollRunStatus.DRAFT,
            created_by_user_id=created_by_user_id,
        )

        skipped: list[uuid.UUID] = []
        total_gross = 0.0
        total_deductions = 0.0
        total_net = 0.0

        as_of = date(period_year, period_month, days_in_month)
        for employee in employees:
            structure = await self.structure_repo.get_active_for_employee(employee.id, as_of)
            if structure is None:
                skipped.append(employee.id)
                continue

            summary = await self.attendance_service.monthly_summary(
                employee.id, organization_id, period_year, period_month
            )
            paid_days = (
                summary["present_days"]
                + summary["half_days"] * 0.5
                + summary["leave_days"]
                + summary["holiday_days"]
                + summary["week_off_days"]
            )
            paid_days = min(paid_days, days_in_month)
            lop_days = round(days_in_month - paid_days, 1)
            proration_factor = paid_days / days_in_month if days_in_month else 1.0

            payslip_lines = []
            gross_amount = 0.0
            deductions_amount = 0.0
            for line in structure.lines:
                component = await self.component_repo.get_by_id(line.salary_component_id, organization_id)
                if component.component_type == SalaryComponentType.EARNING:
                    amount = round(float(line.amount) * proration_factor, 2)
                    gross_amount += amount
                else:
                    amount = float(line.amount)
                    deductions_amount += amount
                payslip_lines.append(
                    {
                        "salary_component_id": component.id,
                        "component_type": component.component_type,
                        "amount": amount,
                    }
                )

            net_amount = round(gross_amount - deductions_amount, 2)
            await self.payslip_repo.create(
                lines=payslip_lines,
                payroll_run_id=run.id,
                employee_id=employee.id,
                salary_structure_id=structure.id,
                days_in_month=days_in_month,
                paid_days=round(paid_days, 1),
                lop_days=lop_days,
                gross_amount=round(gross_amount, 2),
                total_deductions=round(deductions_amount, 2),
                net_amount=net_amount,
            )
            total_gross += gross_amount
            total_deductions += deductions_amount
            total_net += net_amount

        updated_run = await self.run_repo.update(
            run,
            total_gross_amount=round(total_gross, 2),
            total_deductions_amount=round(total_deductions, 2),
            total_net_amount=round(total_net, 2),
        )
        logger.info(
            "payroll_run_generated",
            run_id=str(run.id),
            employees_processed=len(employees) - len(skipped),
            employees_skipped=len(skipped),
        )
        return updated_run, len(employees) - len(skipped), skipped

    async def get_run(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> PayrollRun:
        run = await self.run_repo.get_by_id(run_id, organization_id)
        if not run:
            raise NotFoundError("Payroll run", run_id)
        return run

    async def list_runs(self, organization_id: uuid.UUID, **filters) -> tuple[list[PayrollRun], int]:
        return await self.run_repo.list_for_organization(organization_id, **filters)

    async def list_payslips(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> list[Payslip]:
        await self.get_run(run_id, organization_id)
        return await self.payslip_repo.list_for_run(run_id)

    async def get_payslip(self, payslip_id: uuid.UUID) -> Payslip:
        payslip = await self.payslip_repo.get_by_id(payslip_id)
        if not payslip:
            raise NotFoundError("Payslip", payslip_id)
        return payslip

    async def list_payslips_for_employee(self, employee_id: uuid.UUID, organization_id: uuid.UUID, **filters):
        employee = await self.employee_repo.get_by_id(employee_id, organization_id)
        if not employee:
            raise NotFoundError("Employee", employee_id)
        return await self.payslip_repo.list_for_employee(employee_id, **filters)

    async def finalize_run(
        self,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
        net_payable_account_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None = None,
    ) -> PayrollRun:
        run = await self.get_run(run_id, organization_id)
        if run.status != PayrollRunStatus.DRAFT:
            raise ValidationError(f"Only draft payroll runs can be finalized (this one is '{run.status.value}').")

        payslips = await self.payslip_repo.list_for_run(run_id)
        if not payslips:
            raise ValidationError("This payroll run has no payslips to finalize.")

        net_payable_account = await self.account_repo.get_by_id(net_payable_account_id, organization_id)
        if not net_payable_account:
            raise NotFoundError("Net payable GL account", net_payable_account_id)

        gl_totals: dict[uuid.UUID, dict[str, float]] = {}
        for payslip in payslips:
            for line in payslip.lines:
                component = await self.component_repo.get_by_id(line.salary_component_id, organization_id)
                bucket = gl_totals.setdefault(component.gl_account_id, {"debit": 0.0, "credit": 0.0})
                if line.component_type == SalaryComponentType.EARNING:
                    bucket["debit"] += float(line.amount)
                else:
                    bucket["credit"] += float(line.amount)

        journal_lines = []
        for account_id, totals in gl_totals.items():
            if totals["debit"] > 0:
                journal_lines.append({"account_id": account_id, "debit": round(totals["debit"], 2), "credit": 0})
            if totals["credit"] > 0:
                journal_lines.append({"account_id": account_id, "debit": 0, "credit": round(totals["credit"], 2)})
        journal_lines.append(
            {"account_id": net_payable_account_id, "debit": 0, "credit": float(run.total_net_amount)}
        )

        entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=datetime.combine(run.run_date, datetime.min.time(), tzinfo=timezone.utc),
            memo=f"Payroll {run.period_year}-{run.period_month:02d}",
            source_module=JournalSourceModule.PAYROLL,
            source_id=run.id,
            lines=journal_lines,
            branch_id=run.branch_id,
            created_by_user_id=created_by_user_id,
        )

        updated = await self.run_repo.update(
            run,
            status=PayrollRunStatus.FINALIZED,
            net_payable_account_id=net_payable_account_id,
            journal_entry_id=entry.id,
            finalized_at=datetime.now(timezone.utc),
        )
        logger.info("payroll_run_finalized", run_id=str(run_id), journal_entry_id=str(entry.id))
        return updated

    async def mark_paid(
        self,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
        bank_account_id: uuid.UUID,
        payment_date: datetime,
    ) -> PayrollRun:
        run = await self.get_run(run_id, organization_id)
        if run.status != PayrollRunStatus.FINALIZED:
            raise ValidationError(f"Only finalized payroll runs can be marked paid (this one is '{run.status.value}').")

        bank_account = await self.bank_account_repo.get_by_id(bank_account_id, organization_id)
        if not bank_account:
            raise NotFoundError("Bank account", bank_account_id)

        entry = await self.journal_service.post_transaction(
            organization_id=organization_id,
            entry_date=payment_date,
            memo=f"Payroll disbursement {run.period_year}-{run.period_month:02d}",
            source_module=JournalSourceModule.PAYROLL,
            source_id=run.id,
            lines=[
                {"account_id": run.net_payable_account_id, "debit": float(run.total_net_amount), "credit": 0},
                {"account_id": bank_account.gl_account_id, "debit": 0, "credit": float(run.total_net_amount)},
            ],
            branch_id=run.branch_id,
        )

        await self.bank_service.record_linked_transaction(
            bank_account_id=bank_account_id,
            journal_entry_id=entry.id,
            transaction_date=payment_date,
            description=f"Payroll disbursement {run.period_year}-{run.period_month:02d}",
            debit_amount=0,
            credit_amount=float(run.total_net_amount),
            source=BankTransactionSource.PAYMENT,
            source_id=run.id,
        )

        updated = await self.run_repo.update(
            run,
            status=PayrollRunStatus.PAID,
            bank_account_id=bank_account_id,
            payment_journal_entry_id=entry.id,
            paid_at=datetime.now(timezone.utc),
        )
        logger.info("payroll_run_paid", run_id=str(run_id))
        return updated

    async def cancel_run(self, run_id: uuid.UUID, organization_id: uuid.UUID) -> PayrollRun:
        run = await self.get_run(run_id, organization_id)
        if run.status == PayrollRunStatus.PAID:
            raise ValidationError("A paid payroll run cannot be cancelled.")
        if run.status == PayrollRunStatus.CANCELLED:
            raise ValidationError("This payroll run is already cancelled.")

        if run.journal_entry_id is not None:
            await self.journal_service.reverse_entry(
                run.journal_entry_id,
                organization_id,
                memo=f"Cancellation of payroll run {run.period_year}-{run.period_month:02d}",
            )

        updated = await self.run_repo.update(run, status=PayrollRunStatus.CANCELLED)
        logger.info("payroll_run_cancelled", run_id=str(run_id))
        return updated
