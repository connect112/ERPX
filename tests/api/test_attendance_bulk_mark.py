"""
API tests for POST /attendance/bulk-mark — a whole-date-range backfill/
correction in one call, built for onboarding an employee whose real
start predates their ERPX record (see modules/attendance/service.py's
bulk_mark_attendance) rather than one /mark request per day.
"""

import uuid

import pytest

pytestmark = pytest.mark.api


async def _create_department_and_designation(client, auth_headers, code):
    dept_resp = await client.post(
        "/api/v1/hr/departments",
        json={"name": f"Dept {code}", "code": code},
        headers=auth_headers,
    )
    assert dept_resp.status_code == 201, dept_resp.text
    designation_resp = await client.post(
        "/api/v1/hr/designations",
        json={"title": f"Role {code}", "code": code},
        headers=auth_headers,
    )
    assert designation_resp.status_code == 201, designation_resp.text
    return dept_resp.json(), designation_resp.json()


async def _create_employee(client, auth_headers, department, designation, unique):
    resp = await client.post(
        "/api/v1/employees",
        json={
            "full_name": f"Attendance Test Employee {unique}",
            "email": f"attendance-test.{unique}@example.com",
            "date_of_joining": "2026-01-01",
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def bulk_mark_employee(client, auth_headers):
    unique = uuid.uuid4().hex[:8]
    department, designation = await _create_department_and_designation(client, auth_headers, unique[:6].upper())
    return await _create_employee(client, auth_headers, department, designation, unique)


async def test_bulk_mark_marks_sundays_as_week_off_automatically(client, auth_headers, bulk_mark_employee):
    # January 2026: Sundays fall on the 4th, 11th, 18th, 25th.
    response = await client.post(
        "/api/v1/attendance/bulk-mark",
        json={
            "employee_id": bulk_mark_employee["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "default_status": "present",
            "auto_week_off_sundays": True,
            "exceptions": [],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["days_marked"] == 31

    summary_resp = await client.get(
        f"/api/v1/attendance/employees/{bulk_mark_employee['id']}/summary",
        params={"year": 2026, "month": 1},
        headers=auth_headers,
    )
    assert summary_resp.status_code == 200, summary_resp.text
    summary = summary_resp.json()
    assert summary["week_off_days"] == 4
    assert summary["present_days"] == 27


async def test_bulk_mark_applies_exception_block_over_default(client, auth_headers, bulk_mark_employee):
    response = await client.post(
        "/api/v1/attendance/bulk-mark",
        json={
            "employee_id": bulk_mark_employee["id"],
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
            "default_status": "present",
            "auto_week_off_sundays": True,
            "exceptions": [
                {"start_date": "2026-02-10", "end_date": "2026-02-27", "status": "absent", "remarks": "Extended leave"}
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    summary_resp = await client.get(
        f"/api/v1/attendance/employees/{bulk_mark_employee['id']}/summary",
        params={"year": 2026, "month": 2},
        headers=auth_headers,
    )
    summary = summary_resp.json()
    # Feb 2026 Sundays: 1, 8, 15, 22. The exception block (10th-27th,
    # 18 days) unconditionally overrides the default/week-off pass —
    # including the two Sundays that fall inside it (15th, 22nd) — so
    # only the two Sundays *outside* the block (1st, 8th) stay WEEK_OFF.
    assert summary["week_off_days"] == 2
    assert summary["absent_days"] == 18
    assert summary["present_days"] == 8
