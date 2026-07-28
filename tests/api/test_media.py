"""
API tests for the Media module — albums plus the two-phase asset upload
flow (presigned PUT -> browser-side upload -> confirm) against a real
MinIO instance, mirroring modules.documents' pattern but scoped to
albums with captions. Requires MINIO_ENDPOINT (and friends) to point at
a reachable MinIO — see tests/README.md.
"""

import httpx
import pytest

pytestmark = pytest.mark.api


async def _create_album(client, auth_headers, **overrides):
    payload = {"title": "Hackathon 2026 Photos"}
    payload.update(overrides)
    response = await client.post("/api/v1/media/albums", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _upload_and_confirm(
    client, auth_headers, album_id, *, content: bytes = b"hello world", filename="photo.jpg",
    content_type="image/jpeg", caption=None,
):
    presign_response = await client.post(
        f"/api/v1/media/albums/{album_id}/assets/presigned-upload",
        json={"filename": filename, "content_type": content_type, "caption": caption},
        headers=auth_headers,
    )
    assert presign_response.status_code == 200, presign_response.text
    body = presign_response.json()
    asset_id = body["asset_id"]
    upload_url = body["upload_url"]

    async with httpx.AsyncClient() as raw_client:
        put_response = await raw_client.put(
            upload_url, content=content, headers={"Content-Type": content_type}
        )
        assert put_response.status_code == 200, put_response.text

    confirm_response = await client.post(f"/api/v1/media/assets/{asset_id}/confirm", headers=auth_headers)
    return asset_id, confirm_response


async def test_create_and_list_album(client, auth_headers):
    album = await _create_album(client, auth_headers)
    assert album["title"] == "Hackathon 2026 Photos"

    list_response = await client.get("/api/v1/media/albums", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(a["id"] == album["id"] for a in list_response.json()["items"])


async def test_staff_without_permission_cannot_manage_media(client, staff_headers):
    response = await client.post(
        "/api/v1/media/albums", json={"title": "Unauthorized Album"}, headers=staff_headers
    )
    assert response.status_code == 403


async def test_full_asset_upload_lifecycle(client, auth_headers):
    album = await _create_album(client, auth_headers)
    asset_id, confirm_response = await _upload_and_confirm(
        client, auth_headers, album["id"], content=b"the quick brown fox", caption="Team photo"
    )
    assert confirm_response.status_code == 200
    body = confirm_response.json()
    assert body["status"] == "uploaded"
    assert body["size_bytes"] == len(b"the quick brown fox")
    assert body["caption"] == "Team photo"

    list_response = await client.get(f"/api/v1/media/albums/{album['id']}/assets", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(a["id"] == asset_id for a in list_response.json())

    download_response = await client.get(
        f"/api/v1/media/assets/{asset_id}/download-url", headers=auth_headers
    )
    assert download_response.status_code == 200
    download_url = download_response.json()["download_url"]

    async with httpx.AsyncClient() as raw_client:
        fetched = await raw_client.get(download_url)
        assert fetched.status_code == 200
        assert fetched.content == b"the quick brown fox"


async def test_pending_asset_is_not_listed(client, auth_headers):
    album = await _create_album(client, auth_headers)
    await client.post(
        f"/api/v1/media/albums/{album['id']}/assets/presigned-upload",
        json={"filename": "pending.jpg", "content_type": "image/jpeg"},
        headers=auth_headers,
    )

    list_response = await client.get(f"/api/v1/media/albums/{album['id']}/assets", headers=auth_headers)
    assert list_response.json() == []


async def test_update_asset_caption(client, auth_headers):
    album = await _create_album(client, auth_headers)
    asset_id, confirm_response = await _upload_and_confirm(client, auth_headers, album["id"])
    assert confirm_response.status_code == 200

    update_response = await client.patch(
        f"/api/v1/media/assets/{asset_id}", json={"caption": "Updated caption"}, headers=auth_headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["caption"] == "Updated caption"


async def test_deleting_album_removes_assets_from_storage(client, auth_headers):
    album = await _create_album(client, auth_headers)
    asset_id, confirm_response = await _upload_and_confirm(client, auth_headers, album["id"])
    assert confirm_response.status_code == 200

    delete_response = await client.delete(f"/api/v1/media/albums/{album['id']}", headers=auth_headers)
    assert delete_response.status_code == 200

    get_album_response = await client.get(f"/api/v1/media/albums/{album['id']}", headers=auth_headers)
    assert get_album_response.status_code == 404

    download_response = await client.get(
        f"/api/v1/media/assets/{asset_id}/download-url", headers=auth_headers
    )
    assert download_response.status_code == 404


async def test_oversized_upload_is_rejected_and_cleaned_up(client, auth_headers, monkeypatch):
    import modules.media.service as service_module

    monkeypatch.setattr(service_module, "MAX_UPLOAD_SIZE_BYTES", 10)

    album = await _create_album(client, auth_headers)
    asset_id, confirm_response = await _upload_and_confirm(
        client, auth_headers, album["id"], content=b"this content is definitely more than ten bytes"
    )
    assert confirm_response.status_code == 422

    download_response = await client.get(
        f"/api/v1/media/assets/{asset_id}/download-url", headers=auth_headers
    )
    assert download_response.status_code == 404
