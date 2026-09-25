"""API tests for the org-wide HR settings endpoint (currently just
week_off_days) — modules/hr/routes.py's GET/PATCH /hr/settings.
"""

import pytest

pytestmark = pytest.mark.api


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
