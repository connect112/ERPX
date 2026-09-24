"""
Employees module — FastAPI dependencies.

`get_current_employee` is what every self-service "me" endpoint (employee
portal: my profile, my payslips, ...) depends on instead of an RBAC
permission check — an employee doesn't need `payroll.runs.view` to see
their *own* payslips, owning the record is the authorization. Staff/admin
endpoints viewing arbitrary employees' data continue to use
`require_permissions(...)` exactly as before; this is additive, mirrors
modules/students/dependencies.py's identical pattern for students.
"""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.employees.models import Employee
from modules.employees.repository import EmployeeRepository


async def get_current_employee(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    repo = EmployeeRepository(db)
    employee = await repo.get_by_user_id(user.id)
    if not employee:
        raise ValidationError(
            "Your account is not linked to an employee record. Contact your administrator."
        )
    return employee


async def get_current_employee_organization_id(
    employee: Employee = Depends(get_current_employee),
) -> uuid.UUID:
    return employee.organization_id
