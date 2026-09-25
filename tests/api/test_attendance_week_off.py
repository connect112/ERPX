"""A day with no attendance record at all is normally unpaid (LOP) for
payroll proration — except a recurring weekly off (e.g. Sunday), which is
an organization policy fact, not something an employee "checks in" for.
Self check-in only ever creates a record for a day actually worked, so
without this, every week-off day would silently count against the
employee. See modules/attendance/service.py's monthly_summary and
Organization.week_off_days.
"""

import calendar
import uuid
from datetime import date

import pytest

from modules.attendance.models import AttendanceStatus
from modules.attendance.repository import AttendanceRepository
from modules.employees.repository import EmployeeRepository
from modules.organizations.repository import OrganizationRepository

pytestmark = pytest.mark.api


async def _create_employee(db_session, organization, full_name="Week Off Test Employee"):
    unique = uuid.uuid4().hex[:8]
    employee = await EmployeeRepository(db_session).create(
        organization_id=organization.id,
        full_name=f"{full_name} {unique}",
        date_of_joining=date(2024, 1, 1),
    )
    await db_session.flush()
    return employee


async def test_monthly_summary_counts_unmarked_sundays_as_week_off(
    client, db_session, organization, auth_headers
):
    employee = await _create_employee(db_session, organization)

    year, month = 2026, 8
    days_in_month = calendar.monthrange(year, month)[1]
    sundays = [d for d in range(1, days_in_month + 1) if date(year, month, d).weekday() == 6]
    workdays = [d for d in range(1, days_in_month + 1) if d not in sundays]

    repo = AttendanceRepository(db_session)
    for day in workdays:
        await repo.create(
            organization_id=organization.id,
            employee_id=employee.id,
            attendance_date=date(year, month, day),
            status=AttendanceStatus.PRESENT,
        )

    resp = await client.get(
        f"/api/v1/attendance/employees/{employee.id}/summary",
        params={"year": year, "month": month},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    assert summary["present_days"] == len(workdays)
    assert summary["week_off_days"] == len(sundays)
    assert summary["present_days"] + summary["week_off_days"] == days_in_month


async def test_monthly_summary_respects_org_with_no_week_off_days(
    client, db_session, organization, auth_headers
):
    await OrganizationRepository(db_session).update(organization, week_off_days=[])
    employee = await _create_employee(db_session, organization)

    year, month = 2026, 8
    days_in_month = calendar.monthrange(year, month)[1]
    repo = AttendanceRepository(db_session)
    await repo.create(
        organization_id=organization.id,
        employee_id=employee.id,
        attendance_date=date(year, month, 3),
        status=AttendanceStatus.PRESENT,
    )

    resp = await client.get(
        f"/api/v1/attendance/employees/{employee.id}/summary",
        params={"year": year, "month": month},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    assert summary["present_days"] == 1
    assert summary["week_off_days"] == 0
    assert summary["present_days"] + summary["week_off_days"] < days_in_month
