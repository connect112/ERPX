"""
API tests for the Backups module — triggers a real `pg_dump` against the
live test database and uploads the result to real MinIO, mirroring
modules.media/modules.documents' pattern of testing the actual storage
round-trip rather than mocking it. Requires PG_DUMP_PATH to point at a
real pg_dump binary and MINIO_ENDPOINT to a reachable MinIO — see
tests/README.md.
"""

import httpx
import pytest

pytestmark = pytest.mark.api


async def test_staff_without_permission_cannot_trigger_backup(client, staff_headers):
    response = await client.post("/api/v1/backups", headers=staff_headers)
    assert response.status_code == 403


async def test_trigger_backup_produces_a_real_downloadable_dump(client, auth_headers):
    trigger_response = await client.post("/api/v1/backups", headers=auth_headers)
    assert trigger_response.status_code == 201, trigger_response.text
    job = trigger_response.json()
    assert job["status"] == "completed", job.get("error_message")
    assert job["size_bytes"] is not None and job["size_bytes"] > 0
    assert job["storage_key"] is not None

    list_response = await client.get("/api/v1/backups", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(j["id"] == job["id"] for j in list_response.json()["items"])

    download_response = await client.get(f"/api/v1/backups/{job['id']}/download-url", headers=auth_headers)
    assert download_response.status_code == 200
    download_url = download_response.json()["download_url"]

    async with httpx.AsyncClient() as raw_client:
        fetched = await raw_client.get(download_url)
        assert fetched.status_code == 200
        # A real pg_dump text dump starts with a Postgres-generated header comment.
        assert fetched.content.startswith(b"--")


async def test_staff_without_view_permission_cannot_list_backups(client, staff_headers):
    response = await client.get("/api/v1/backups", headers=staff_headers)
    assert response.status_code == 403
