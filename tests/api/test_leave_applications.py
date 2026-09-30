"""API tests for the admin-facing leave application review flow
(modules/leave/routes.py's POST /applications/{id}/approve and /reject).

No test previously exercised approve_leave end-to-end: it calls
AttendanceService.mark_attendance to record each day of an approved
leave as ON_LEAVE, and that method was briefly deleted as a side effect
of removing admin-triggered attendance marking (PR #38) -- an
AttributeError on every leave approval, live in production, with
nothing catching it. This file exists specifically to make sure that
class of regression can't happen silently again.
"""

import uuid
from datetime import date, timedelta

import pytest

from modules.attendance.models import AttendanceStatus
from modules.attendance.repository import AttendanceRepository
from modules.employees.repository import EmployeeRepository
from modules.leave.repository import LeaveTypeRepository

pytestmark = pytest.mark.api


@pytest.fixture
async def leave_type(db_session, organization):
    unique = uuid.uuid4().hex[:8]
    return await LeaveTypeRepository(db_session).create(
        organization_id=organization.id,
        name=f"Casual Leave {unique}",
        code=f"CL{unique}",
        annual_quota=12,
    )


@pytest.fixture
async def employee(db_session, organization):
    unique = uuid.uuid4().hex[:8]
    return await EmployeeRepository(db_session).create(
        organization_id=organization.id,
        full_name=f"Leave Test Employee {unique}",
        date_of_joining=date(2024, 1, 1),
    )


async def test_approving_leave_marks_each_day_as_on_leave_in_attendance(
    client, auth_headers, db_session, organization, employee, leave_type
):
    start = date(2026, 10, 5)
    end = date(2026, 10, 7)
    apply_resp = await client.post(
        "/api/v1/leave/applications",
        json={
            "employee_id": str(employee.id),
            "leave_type_id": str(leave_type.id),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reason": "Family function",
        },
        headers=auth_headers,
    )
    assert apply_resp.status_code == 201, apply_resp.text
    application_id = apply_resp.json()["id"]

    approve_resp = await client.post(
        f"/api/v1/leave/applications/{application_id}/approve", headers=auth_headers
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"

    attendance_repo = AttendanceRepository(db_session)
    current = start
    while current <= end:
        record = await attendance_repo.get_for_employee_date(employee.id, current)
        assert record is not None, f"no attendance record created for {current}"
        assert record.status == AttendanceStatus.ON_LEAVE
        current += timedelta(days=1)


async def test_rejecting_leave_does_not_touch_attendance(
    client, auth_headers, db_session, organization, employee, leave_type
):
    start = date(2026, 11, 2)
    end = date(2026, 11, 2)
    apply_resp = await client.post(
        "/api/v1/leave/applications",
        json={
            "employee_id": str(employee.id),
            "leave_type_id": str(leave_type.id),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reason": "Personal",
        },
        headers=auth_headers,
    )
    assert apply_resp.status_code == 201, apply_resp.text
    application_id = apply_resp.json()["id"]

    reject_resp = await client.post(
        f"/api/v1/leave/applications/{application_id}/reject",
        json={"rejection_reason": "Insufficient coverage that week"},
        headers=auth_headers,
    )
    assert reject_resp.status_code == 200, reject_resp.text
    assert reject_resp.json()["status"] == "rejected"

    attendance_repo = AttendanceRepository(db_session)
    record = await attendance_repo.get_for_employee_date(employee.id, start)
    assert record is None
