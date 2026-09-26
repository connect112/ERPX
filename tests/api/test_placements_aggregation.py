"""
API tests for the placements job-aggregation trigger/listing routes. The
`run_aggregation_task.delay` call itself is monkeypatched to a no-op by
`tests/_fixtures.py`'s autouse fixture, so these only verify the HTTP
contract (status code, response shape, access control) — the pipeline logic
itself is covered by `tests/integration/test_placements_aggregation_service.py`
and `tests/unit/test_placements_connectors.py`.
"""

import pytest

pytestmark = pytest.mark.api


async def test_trigger_aggregation_run_returns_202_and_queued_run(client, auth_headers):
    response = await client.post("/api/v1/placements/aggregation/run", headers=auth_headers)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["triggered_by"].startswith("manual:")
    assert body["postings_created"] == 0


async def test_trigger_aggregation_run_requires_manage_permission(client, staff_headers):
    response = await client.post("/api/v1/placements/aggregation/run", headers=staff_headers)

    assert response.status_code == 403


async def test_list_aggregation_runs_requires_view_permission(client, staff_headers):
    response = await client.get("/api/v1/placements/aggregation/runs", headers=staff_headers)

    assert response.status_code == 403


async def test_list_aggregation_runs_includes_triggered_run(client, auth_headers):
    trigger_response = await client.post("/api/v1/placements/aggregation/run", headers=auth_headers)
    assert trigger_response.status_code == 202
    run_id = trigger_response.json()["id"]

    list_response = await client.get("/api/v1/placements/aggregation/runs", headers=auth_headers)

    assert list_response.status_code == 200
    run_ids = [r["id"] for r in list_response.json()]
    assert run_id in run_ids
