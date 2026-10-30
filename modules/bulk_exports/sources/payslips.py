"""
The payslips of one payroll run, each built by ``PayrollService.get_payslip_pdf`` -- the same PDF the single payslip
download returns. Needs ``payroll.runs.view``, the permission that download needs.
"""

import calendar
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.bulk_exports.sources.base import DocumentSource, ExportItem, Placeholder, Scope, matches

PERMISSION = "payroll.runs.view"

_PLACEHOLDERS = (
    Placeholder("employee_name", "Employee name", "Ravi Kumar"),
    Placeholder("employee_code", "Employee code", "EMP-0042"),
    Placeholder("period", "Pay period", "2026-10"),
    Placeholder("month_name", "Month", "October"),
    Placeholder("year", "Year", "2026"),
)


class PayslipsSource(DocumentSource):
    key = "payslips"
    label = "Payslips"
    module = "payroll"
    document_type = "Payslip"
    scope_kind = "payroll_run"
    base_placeholders = _PLACEHOLDERS
    presets = (
        ("Employee code, name, period", "{{employee_code}}_{{employee_name}}_{{period}}.pdf"),
        ("Name and month", "{{employee_name}}_{{month_name}}_{{year}}.pdf"),
    )

    async def open_scope(self, db: AsyncSession, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None) -> Scope:
        from modules.payroll.models import PayrollRun

        if not user.is_superuser and PERMISSION not in await AuthorizationRepository(db).get_permission_codes_for_user(user.id):
            raise AuthorizationError(f"This action requires the following permission(s): {PERMISSION}")
        if scope_id is None:
            raise NotFoundError("Payroll run", "")
        run = (
            await db.execute(select(PayrollRun).where(PayrollRun.id == scope_id, PayrollRun.organization_id == organization_id))
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Payroll run", scope_id)
        period = f"{run.period_year}-{run.period_month:02d}"
        return Scope(id=run.id, label=f"Payroll {period}", organization_id=organization_id, extra={"run": run, "period": period})

    async def query(self, db: AsyncSession, scope: Scope, search: str | None, status: str | None) -> list[ExportItem]:
        from modules.employees.models import Employee
        from modules.payroll.models import Payslip

        run = scope.extra["run"]
        rows = await db.execute(
            select(Payslip, Employee)
            .join(Employee, Employee.id == Payslip.employee_id)
            .where(Payslip.payroll_run_id == run.id, Employee.organization_id == scope.organization_id)
            .order_by(Employee.full_name, Payslip.id)
        )
        items = []
        for payslip, employee in rows.all():
            if not matches(search, employee.full_name, employee.employee_code):
                continue
            items.append(
                ExportItem(
                    id=payslip.id,
                    title=employee.full_name,
                    subtitle=f"{employee.employee_code} · {scope.extra['period']}",
                    status=None,
                    values={
                        "employee_name": employee.full_name,
                        "employee_code": employee.employee_code,
                        "period": scope.extra["period"],
                        "month_name": calendar.month_name[run.period_month],
                        "year": run.period_year,
                    },
                    extension="pdf",
                )
            )
        return items

    async def fetch(self, db: AsyncSession, scope: Scope, item: ExportItem) -> bytes:
        from modules.payroll.service import PayrollService

        return await PayrollService(db).get_payslip_pdf(item.id, scope.organization_id)
