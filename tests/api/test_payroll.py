"""
API tests for the Payroll module additions: adding a one-off line (e.g.
a reimbursement) to a single payslip while its run is still Draft, and
the scheduled auto-generation of a monthly draft run on the last
working day of the month.
"""

import calendar
import uuid
from datetime import date, datetime, timedelta

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


async def _create_bank_account(client, auth_headers, gl_account_id, unique):
    resp = await client.post(
        "/api/v1/accounting/bank/accounts",
        json={
            "gl_account_id": gl_account_id,
            "account_name": f"Bank {unique}",
            "account_number": f"ACC{unique}",
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


async def test_get_payslip_pdf_returns_a_real_pdf(client, auth_headers, db_session, organization, payroll_setup):
    await _mark_present_for_month(db_session, organization.id, payroll_setup["employee"]["id"], 2026, 6)

    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 6, "run_date": "2026-06-30"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]

    payslips_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}/payslips", headers=auth_headers)
    payslip = payslips_resp.json()[0]

    pdf_resp = await client.get(f"/api/v1/payroll/payslips/{payslip['id']}/pdf", headers=auth_headers)
    assert pdf_resp.status_code == 200, pdf_resp.text
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")


async def test_get_payslip_pdf_404s_for_a_payslip_in_another_organization(
    client, auth_headers, db_session, organization, payroll_setup
):
    await _mark_present_for_month(db_session, organization.id, payroll_setup["employee"]["id"], 2026, 7)

    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 7, "run_date": "2026-07-31"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]
    payslips_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}/payslips", headers=auth_headers)
    payslip = payslips_resp.json()[0]

    from app.core.security import create_access_token, hash_password
    from modules.authentication.models import UserStatus
    from modules.authentication.repository import AuthRepository
    from modules.organizations.repository import OrganizationRepository
    from modules.users.repository import UserProfileRepository

    other_org = await OrganizationRepository(db_session).create(
        name="Other Org", slug=f"other-org-{uuid.uuid4().hex[:8]}"
    )
    other_admin = await AuthRepository(db_session).create_user(
        email=f"otheradmin.{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Test1234!"),
        full_name="Other Admin",
    )
    other_admin.status = UserStatus.ACTIVE
    other_admin.is_email_verified = True
    other_admin.is_superuser = True
    await db_session.flush()
    await UserProfileRepository(db_session).create(user_id=other_admin.id, organization_id=other_org.id)
    await db_session.flush()
    other_headers = {"Authorization": f"Bearer {create_access_token(str(other_admin.id))}"}

    pdf_resp = await client.get(
        f"/api/v1/payroll/payslips/{payslip['id']}/pdf", headers=other_headers
    )
    assert pdf_resp.status_code == 404, pdf_resp.text


async def test_employee_can_download_own_payslip_pdf_but_not_someone_elses(
    client, auth_headers, db_session, organization, payroll_setup
):
    await _mark_present_for_month(db_session, organization.id, payroll_setup["employee"]["id"], 2026, 8)

    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 8, "run_date": "2026-08-31"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]
    payslips_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}/payslips", headers=auth_headers)
    payslip = payslips_resp.json()[0]

    invite_resp = await client.post(
        f"/api/v1/employees/{payroll_setup['employee']['id']}/invite", headers=auth_headers
    )
    assert invite_resp.status_code == 200, invite_resp.text
    employee_user_id = invite_resp.json()["user_id"]

    from app.core.security import create_access_token

    employee_headers = {"Authorization": f"Bearer {create_access_token(employee_user_id)}"}

    own_pdf_resp = await client.get(
        f"/api/v1/payroll/payslips/me/{payslip['id']}/pdf", headers=employee_headers
    )
    assert own_pdf_resp.status_code == 200, own_pdf_resp.text
    assert own_pdf_resp.headers["content-type"] == "application/pdf"
    assert own_pdf_resp.content.startswith(b"%PDF")

    # A second employee (no relation to this payslip) can't download it via
    # the self-service route, even within the same organization.
    unique = uuid.uuid4().hex[:8]
    dept_resp = await client.get("/api/v1/hr/departments", headers=auth_headers)
    department_id = dept_resp.json()[0]["id"]
    designation_resp = await client.get("/api/v1/hr/designations", headers=auth_headers)
    designation_id = designation_resp.json()[0]["id"]
    other_employee_resp = await client.post(
        "/api/v1/employees",
        json={
            "full_name": f"Other Employee {unique}",
            "email": f"other-employee.{unique}@example.com",
            "date_of_joining": "2026-01-01",
            "department_id": department_id,
            "designation_id": designation_id,
        },
        headers=auth_headers,
    )
    assert other_employee_resp.status_code == 201, other_employee_resp.text
    other_invite_resp = await client.post(
        f"/api/v1/employees/{other_employee_resp.json()['id']}/invite", headers=auth_headers
    )
    assert other_invite_resp.status_code == 200, other_invite_resp.text
    other_employee_headers = {
        "Authorization": f"Bearer {create_access_token(other_invite_resp.json()['user_id'])}"
    }

    other_pdf_resp = await client.get(
        f"/api/v1/payroll/payslips/me/{payslip['id']}/pdf", headers=other_employee_headers
    )
    assert other_pdf_resp.status_code == 404, other_pdf_resp.text


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


async def test_mark_paid_sets_paid_at_to_the_entered_payment_date(
    client, auth_headers, db_session, organization, payroll_setup
):
    """Backfilling a historical payroll run needs paid_at to reflect the
    real-world payment date the admin enters, not the moment they happened
    to click the button in the app — otherwise the payslip's own date is
    wrong for something like a bank loan verification."""
    await _mark_present_for_month(db_session, organization.id, payroll_setup["employee"]["id"], 2026, 5)

    unique = uuid.uuid4().hex[:8]
    bank_gl_account = await _create_account(client, auth_headers, f"1{unique[:3]}", "Bank", "asset")
    bank_account = await _create_bank_account(client, auth_headers, bank_gl_account["id"], unique)

    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 5, "run_date": "2026-05-31"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]

    finalize_resp = await client.post(
        f"/api/v1/payroll/runs/{run['id']}/finalize",
        json={"net_payable_account_id": payroll_setup["payable_account"]["id"]},
        headers=auth_headers,
    )
    assert finalize_resp.status_code == 200, finalize_resp.text

    mark_paid_resp = await client.post(
        f"/api/v1/payroll/runs/{run['id']}/mark-paid",
        json={"bank_account_id": bank_account["id"], "payment_date": "2026-06-05"},
        headers=auth_headers,
    )
    assert mark_paid_resp.status_code == 200, mark_paid_resp.text
    paid_run = mark_paid_resp.json()
    assert paid_run["status"] == "paid"
    # The entered payment_date is naive and lands on a timezone-aware column,
    # so it round-trips as the same instant as entry_date/transaction_date
    # (which use payment_date the same way) rather than a bare date string —
    # what matters here is that it's the entered date, not datetime.now().
    paid_at = datetime.fromisoformat(paid_run["paid_at"].replace("Z", "+00:00"))
    assert paid_at.date() in (date(2026, 6, 4), date(2026, 6, 5))
    assert not paid_run["paid_at"].startswith(date.today().isoformat())


async def test_generate_run_treats_unmarked_sundays_as_paid_week_off(
    client, auth_headers, db_session, organization, payroll_setup
):
    """Mirrors an employee who only ever self-checks-in on days they
    actually work — no record at all gets created for Sundays. Payroll
    proration must still treat those Sundays as paid via
    Organization.week_off_days, not silently as unpaid LOP."""
    year, month = 2026, 8
    days_in_month = calendar.monthrange(year, month)[1]
    repo = AttendanceRepository(db_session)
    for day in range(1, days_in_month + 1):
        if date(year, month, day).weekday() == 6:
            continue
        await repo.create(
            organization_id=organization.id,
            employee_id=payroll_setup["employee"]["id"],
            attendance_date=date(year, month, day),
            status=AttendanceStatus.PRESENT,
        )

    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": year, "period_month": month, "run_date": f"{year}-{month:02d}-{days_in_month}"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text

    run = generate_resp.json()["run"]
    payslips_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}/payslips", headers=auth_headers)
    payslip = payslips_resp.json()[0]
    assert payslip["lop_days"] == 0
    assert payslip["gross_amount"] == 15000


async def test_deleting_a_cancelled_run_frees_its_period_for_regeneration(client, auth_headers, payroll_setup):
    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 3, "run_date": "2026-03-31"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]

    regenerate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 3, "run_date": "2026-03-31"},
        headers=auth_headers,
    )
    assert regenerate_resp.status_code == 409, regenerate_resp.text

    cancel_resp = await client.post(f"/api/v1/payroll/runs/{run['id']}/cancel", headers=auth_headers)
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelled"

    delete_resp = await client.delete(f"/api/v1/payroll/runs/{run['id']}", headers=auth_headers)
    assert delete_resp.status_code == 204, delete_resp.text

    get_resp = await client.get(f"/api/v1/payroll/runs/{run['id']}", headers=auth_headers)
    assert get_resp.status_code == 404

    regenerate_after_delete_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 3, "run_date": "2026-03-31"},
        headers=auth_headers,
    )
    assert regenerate_after_delete_resp.status_code == 201, regenerate_after_delete_resp.text


async def test_deleting_a_non_cancelled_run_is_rejected(client, auth_headers, payroll_setup):
    generate_resp = await client.post(
        "/api/v1/payroll/runs",
        json={"period_year": 2026, "period_month": 4, "run_date": "2026-04-30"},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    run = generate_resp.json()["run"]
    assert run["status"] == "draft"

    delete_resp = await client.delete(f"/api/v1/payroll/runs/{run['id']}", headers=auth_headers)
    assert delete_resp.status_code == 422, delete_resp.text


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
