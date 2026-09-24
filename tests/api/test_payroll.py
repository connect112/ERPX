"""
API tests for the Payroll module additions: adding a one-off line (e.g.
a reimbursement) to a single payslip while its run is still Draft, and
the scheduled auto-generation of a monthly draft run on the last
working day of the month.
"""

import calendar
import uuid
from datetime import date, timedelta

import pytest

from modules.attendance.models import AttendanceStatus
from modules.attendance.repository import AttendanceRepository
from modules.payroll.service import PayrollService

pytestmark = pytest.mark.api


async def _mark_present_for_month(db_session, organization_id, employee_id, year, month):
    """generate_run prorates gross pay by real Attendance — with none
    recorded, every day reads as LOP and gross comes out to 0. Tests
    that need a real nonzero payslip (e.g. finalizing it into a journal
    entry) need real attendance behind it."""
    repo = AttendanceRepository(db_session)
    days_in_month = calendar.monthrange(year, month)[1]
    for day in range(1, days_in_month + 1):
        await repo.create(
            organization_id=organization_id,
            employee_id=employee_id,
            attendance_date=date(year, month, day),
            status=AttendanceStatus.PRESENT,
        )


async def _create_account(client, auth_headers, code, name, account_type):
    response = await client.post(
        "/api/v1/accounting/accounts",
        json={"code": code, "name": name, "account_type": account_type},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


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
            "full_name": f"Payroll Test Employee {unique}",
            "email": f"payroll-test.{unique}@example.com",
            "date_of_joining": "2026-01-01",
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_component(client, auth_headers, gl_account_id, unique, component_type="earning"):
    resp = await client.post(
        "/api/v1/payroll/components",
        json={
            "name": f"Component {unique}",
            "code": f"COMP{unique}",
            "gl_account_id": gl_account_id,
            "component_type": component_type,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_structure(client, auth_headers, employee_id, component_id, amount, effective_from="2026-01-01"):
    resp = await client.post(
        "/api/v1/payroll/structures",
        json={
            "employee_id": employee_id,
            "effective_from": effective_from,
            "lines": [{"salary_component_id": component_id, "amount": amount}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def payroll_setup(client, auth_headers):
    unique = uuid.uuid4().hex[:8]
    expense_account = await _create_account(client, auth_headers, f"5{unique[:3]}", "Salary Expense", "expense")
    payable_account = await _create_account(client, auth_headers, f"2{unique[:3]}", "Reimbursements Payable", "liability")
    department, designation = await _create_department_and_designation(client, auth_headers, unique[:6].upper())
    employee = await _create_employee(client, auth_headers, department, designation, unique)
    basic_component = await _create_component(client, auth_headers, expense_account["id"], f"{unique}B", "earning")
    reimbursement_component = await _create_component(
        client, auth_headers, expense_account["id"], f"{unique}R", "earning"
    )
    await _create_structure(client, auth_headers, employee["id"], basic_component["id"], 15000)
    return {
        "employee": employee,
        "expense_account": expense_account,
        "payable_account": payable_account,
        "basic_component": basic_component,
        "reimbursement_component": reimbursement_component,
    }


async def test_add_payslip_line_on_draft_run_updates_totals(client, auth_headers, payroll_setup):
    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 1, "run_date": "2026-01-31"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]
    assert run["status"] == "draft"

    payslips_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}/payslips", headers=auth_headers)
    assert payslips_resp.status_code == 200, payslips_resp.text
    payslips = payslips_resp.json()
    assert len(payslips) == 1
    payslip = payslips[0]
    original_gross = payslip["gross_amount"]
    original_net = payslip["net_amount"]

    add_line_resp = await client.post(
        f"/api/v1/payroll/payslips/{payslip['id']}/lines",
        json={"salary_component_id": payroll_setup["reimbursement_component"]["id"], "amount": 1005.90},
        headers=auth_headers,
    )
    assert add_line_resp.status_code == 200, add_line_resp.text
    updated_payslip = add_line_resp.json()
    assert updated_payslip["gross_amount"] == round(original_gross + 1005.90, 2)
    assert updated_payslip["net_amount"] == round(original_net + 1005.90, 2)
    assert len(updated_payslip["lines"]) == 2

    run_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}", headers=auth_headers)
    assert run_resp.status_code == 200, run_resp.text
    updated_run = run_resp.json()
    assert updated_run["total_gross_amount"] == round(run["total_gross_amount"] + 1005.90, 2)
    assert updated_run["total_net_amount"] == round(run["total_net_amount"] + 1005.90, 2)


async def test_add_payslip_line_rejected_once_run_is_finalized(
    client, auth_headers, db_session, organization, payroll_setup
):
    await _mark_present_for_month(db_session, organization.id, payroll_setup["employee"]["id"], 2026, 2)

    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 2, "run_date": "2026-02-28"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]

    payslips_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}/payslips", headers=auth_headers)
    payslip = payslips_resp.json()[0]

    finalize_resp = await client.post(
        f"/api/v1/payroll/runs/{run['id']}/finalize",
        json={"net_payable_account_id": payroll_setup["payable_account"]["id"]},
        headers=auth_headers,
    )
    assert finalize_resp.status_code == 200, finalize_resp.text

    add_line_resp = await client.post(
        f"/api/v1/payroll/payslips/{payslip['id']}/lines",
        json={"salary_component_id": payroll_setup["reimbursement_component"]["id"], "amount": 500},
        headers=auth_headers,
    )
    assert add_line_resp.status_code == 422, add_line_resp.text


async def test_auto_generate_monthly_draft_only_on_last_working_day(client, db_session, organization, payroll_setup):
    def _last_working_day(year: int, month: int) -> date:
        last = calendar.monthrange(year, month)[1]
        d = date(year, month, last)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d

    service = PayrollService(db_session)
    last_working_day = _last_working_day(2026, 3)
    not_last_working_day = last_working_day - timedelta(days=1)

    no_op_result = await service.auto_generate_monthly_draft(organization.id, today=not_last_working_day)
    assert no_op_result is None

    generated_run = await service.auto_generate_monthly_draft(organization.id, today=last_working_day)
    assert generated_run is not None
    assert generated_run.period_year == 2026
    assert generated_run.period_month == 3
    assert generated_run.status.value == "draft"

    already_exists_result = await service.auto_generate_monthly_draft(organization.id, today=last_working_day)
    assert already_exists_result is None
