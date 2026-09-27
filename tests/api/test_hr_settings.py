"""API tests for the org-wide HR settings endpoint — modules/hr/routes.py's
GET/PATCH /hr/settings. Covers week_off_days plus the two payroll-automation
settings (default_salary_payable_account_id, default_expense_reimbursement_component_id)
that turn on modules/payroll/tasks.py's automatic finalize+email pipeline.
"""

import uuid

import pytest

pytestmark = pytest.mark.api


async def _create_account(client, auth_headers, code, name, account_type):
    resp = await client.post(
        "/api/v1/accounting/accounts",
        json={"code": code, "name": name, "account_type": account_type},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_component(client, auth_headers, gl_account_id, code, component_type):
    resp = await client.post(
        "/api/v1/payroll/components",
        json={"name": f"Component {code}", "code": code, "gl_account_id": gl_account_id, "component_type": component_type},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_get_hr_settings_defaults_to_sunday_only(client, auth_headers):
    resp = await client.get("/api/v1/hr/settings", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["week_off_days"] == [6]


async def test_update_hr_settings_changes_week_off_days(client, auth_headers):
    update_resp = await client.patch(
        "/api/v1/hr/settings", json={"week_off_days": [6, 0]}, headers=auth_headers
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["week_off_days"] == [0, 6]

    get_resp = await client.get("/api/v1/hr/settings", headers=auth_headers)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["week_off_days"] == [0, 6]


async def test_update_hr_settings_rejects_invalid_weekday(client, auth_headers):
    resp = await client.patch("/api/v1/hr/settings", json={"week_off_days": [7]}, headers=auth_headers)
    assert resp.status_code == 422, resp.text


async def test_update_hr_settings_allows_clearing_week_offs(client, auth_headers):
    resp = await client.patch("/api/v1/hr/settings", json={"week_off_days": []}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["week_off_days"] == []


async def test_default_salary_payable_account_defaults_to_none(client, auth_headers):
    resp = await client.get("/api/v1/hr/settings", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["default_salary_payable_account_id"] is None
    assert resp.json()["default_expense_reimbursement_component_id"] is None


async def test_update_default_salary_payable_account_requires_liability_type(client, auth_headers):
    unique = uuid.uuid4().hex[:6]
    expense_account = await _create_account(client, auth_headers, f"5{unique}", "Salary Expense", "expense")

    bad_resp = await client.patch(
        "/api/v1/hr/settings",
        json={"default_salary_payable_account_id": expense_account["id"]},
        headers=auth_headers,
    )
    assert bad_resp.status_code == 422, bad_resp.text

    liability_account = await _create_account(client, auth_headers, f"2{unique}", "Salary Payable", "liability")
    good_resp = await client.patch(
        "/api/v1/hr/settings",
        json={"default_salary_payable_account_id": liability_account["id"]},
        headers=auth_headers,
    )
    assert good_resp.status_code == 200, good_resp.text
    assert good_resp.json()["default_salary_payable_account_id"] == liability_account["id"]


async def test_update_default_expense_reimbursement_component_requires_active_earning_type(
    client, auth_headers
):
    unique = uuid.uuid4().hex[:6]
    expense_account = await _create_account(client, auth_headers, f"5{unique}", "Salary Expense", "expense")
    deduction_component = await _create_component(
        client, auth_headers, expense_account["id"], f"D{unique}", "deduction"
    )

    bad_resp = await client.patch(
        "/api/v1/hr/settings",
        json={"default_expense_reimbursement_component_id": deduction_component["id"]},
        headers=auth_headers,
    )
    assert bad_resp.status_code == 422, bad_resp.text

    earning_component = await _create_component(client, auth_headers, expense_account["id"], f"E{unique}", "earning")
    good_resp = await client.patch(
        "/api/v1/hr/settings",
        json={"default_expense_reimbursement_component_id": earning_component["id"]},
        headers=auth_headers,
    )
    assert good_resp.status_code == 200, good_resp.text
    assert good_resp.json()["default_expense_reimbursement_component_id"] == earning_component["id"]
