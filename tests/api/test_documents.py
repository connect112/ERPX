"""
API tests for the Documents module — exercises the real two-phase upload
flow (presigned PUT -> browser-side upload -> confirm) against a real
MinIO instance, not a mock. Requires MINIO_ENDPOINT (and friends) to point
at a reachable MinIO — see tests/README.md.
"""

import httpx
import pytest

pytestmark = pytest.mark.api


async def _upload_and_confirm(client, auth_headers, *, content: bytes = b"hello world", filename="test.txt", content_type="text/plain", entity_type="corporate_clients", entity_id=None):
    import uuid

    entity_id = entity_id or str(uuid.uuid4())
    presign_response = await client.post(
        "/api/v1/documents/presigned-upload",
        json={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "filename": filename,
            "content_type": content_type,
        },
        headers=auth_headers,
    )
    assert presign_response.status_code == 200
    body = presign_response.json()
    document_id = body["document_id"]
    upload_url = body["upload_url"]

    async with httpx.AsyncClient() as raw_client:
        put_response = await raw_client.put(
            upload_url, content=content, headers={"Content-Type": content_type}
        )
        assert put_response.status_code == 200, put_response.text

    confirm_response = await client.post(f"/api/v1/documents/{document_id}/confirm", headers=auth_headers)
    return document_id, entity_id, confirm_response


async def test_full_upload_lifecycle(client, auth_headers):
    document_id, entity_id, confirm_response = await _upload_and_confirm(
        client, auth_headers, content=b"the quick brown fox"
    )
    assert confirm_response.status_code == 200
    body = confirm_response.json()
    assert body["status"] == "uploaded"
    assert body["size_bytes"] == len(b"the quick brown fox")

    list_response = await client.get(
        f"/api/v1/documents?entity_type=corporate_clients&entity_id={entity_id}", headers=auth_headers
    )
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(d["id"] == document_id for d in items)

    download_response = await client.get(
        f"/api/v1/documents/{document_id}/download-url", headers=auth_headers
    )
    assert download_response.status_code == 200
    download_url = download_response.json()["download_url"]

    async with httpx.AsyncClient() as raw_client:
        fetched = await raw_client.get(download_url)
        assert fetched.status_code == 200
        assert fetched.content == b"the quick brown fox"


async def test_confirming_before_upload_is_rejected(client, auth_headers):
    presign_response = await client.post(
        "/api/v1/documents/presigned-upload",
        json={"entity_type": "corporate_clients", "filename": "never.txt", "content_type": "text/plain"},
        headers=auth_headers,
    )
    document_id = presign_response.json()["document_id"]

    confirm_response = await client.post(f"/api/v1/documents/{document_id}/confirm", headers=auth_headers)
    assert confirm_response.status_code == 422


async def test_pending_upload_is_not_listed(client, auth_headers):
    import uuid

    entity_id = str(uuid.uuid4())
    await client.post(
        "/api/v1/documents/presigned-upload",
        json={
            "entity_type": "corporate_clients",
            "entity_id": entity_id,
            "filename": "pending.txt",
            "content_type": "text/plain",
        },
        headers=auth_headers,
    )

    list_response = await client.get(
        f"/api/v1/documents?entity_type=corporate_clients&entity_id={entity_id}", headers=auth_headers
    )
    assert list_response.json() == []


async def test_deleting_a_document_removes_it_from_storage(client, auth_headers):
    document_id, entity_id, confirm_response = await _upload_and_confirm(client, auth_headers)
    assert confirm_response.status_code == 200

    delete_response = await client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers)
    assert delete_response.status_code == 200

    list_response = await client.get(
        f"/api/v1/documents?entity_type=corporate_clients&entity_id={entity_id}", headers=auth_headers
    )
    assert list_response.json() == []

    download_response = await client.get(
        f"/api/v1/documents/{document_id}/download-url", headers=auth_headers
    )
    assert download_response.status_code == 404


async def test_oversized_upload_is_rejected_and_cleaned_up(client, auth_headers, monkeypatch):
    import modules.documents.service as service_module

    monkeypatch.setattr(service_module, "MAX_UPLOAD_SIZE_BYTES", 10)

    document_id, entity_id, confirm_response = await _upload_and_confirm(
        client, auth_headers, content=b"this content is definitely more than ten bytes"
    )
    assert confirm_response.status_code == 422

    # The oversized document should have been deleted, not left dangling.
    get_response = await client.get(
        f"/api/v1/documents/{document_id}/download-url", headers=auth_headers
    )
    assert get_response.status_code == 404


async def test_staff_without_documents_permission_is_forbidden(client, staff_headers):
    response = await client.get(
        "/api/v1/documents?entity_type=corporate_clients&entity_id=00000000-0000-0000-0000-000000000000",
        headers=staff_headers,
    )
    assert response.status_code == 403


async def test_path_traversal_characters_in_filename_and_entity_type_are_neutralized(
    client, auth_headers, db_session, organization
):
    """A caller-supplied `filename`/`entity_type` shouldn't be able to steer
    the storage key's path structure — e.g. escape the org-scoped prefix via
    "../" or embed extra "/" segments. This is defense-in-depth (RBAC + the
    org-scoped lookup are the real access control) but the key itself should
    still come out confined to the expected `{org}/{entity_type}/{entity}/...`
    shape with no literal "/" or ".." left over from user input."""
    import uuid as uuid_module

    from modules.documents.repository import DocumentRepository

    document_id, entity_id, confirm_response = await _upload_and_confirm(
        client,
        auth_headers,
        content=b"payload",
        filename="../../../etc/passwd",
        entity_type="../../other-org",
    )
    assert confirm_response.status_code == 200

    # The upload/confirm/download round trip still works end-to-end even
    # though the inputs were hostile — sanitizing the key shouldn't break
    # the feature for a malicious-looking but otherwise normal request.
    download_response = await client.get(
        f"/api/v1/documents/{document_id}/download-url", headers=auth_headers
    )
    assert download_response.status_code == 200

    repo = DocumentRepository(db_session)
    document = await repo.get_by_id(uuid_module.UUID(document_id), organization.id)
    assert document is not None
    assert "/../" not in document.storage_key
    assert not document.storage_key.startswith("../")
    assert not document.storage_key.startswith("/")
    # Exactly three "/" separators: org / entity_type / entity_id-or-unattached / key-tail
    assert document.storage_key.count("/") == 3
