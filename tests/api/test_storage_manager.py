"""
Storage Manager API tests. Real database and real MinIO, synthetic files only: every object a test creates carries a
unique token in its key, and a fixture removes anything carrying it afterwards (including copies in `.trash/`).
"""

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.config import settings
from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.documents.models import Document
from modules.institutions.models import Institution
from modules.organizations.repository import OrganizationRepository
from modules.storage_manager import registry
from modules.storage_manager.service import ObjectStore, decode_orphan_id, encode_orphan_id
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

BASE = "/api/v1/storage-manager"


@pytest_asyncio.fixture
async def token():
    token = f"smtest-{uuid.uuid4().hex[:10]}"
    yield token
    store = ObjectStore()
    for key in list(await store.list_all()):
        if token in key:
            await store.remove(key)


@pytest_asyncio.fixture
async def store():
    return ObjectStore()


async def put(store, key, data=b"synthetic test file", content_type="text/plain"):
    import asyncio

    await asyncio.to_thread(store._client.put_object, store.bucket, key, io.BytesIO(data), len(data), content_type=content_type)


async def admin_headers(db_session, organization, permissions=("storage.view",)):
    user, tok = await _make_user(db_session, organization, is_superuser=False,
                                 email=f"adm-{uuid.uuid4().hex[:8]}@erpx.example.com")
    repo = AuthorizationRepository(db_session)
    role = await repo.create_role(f"Role {uuid.uuid4().hex[:6]}", f"role-{uuid.uuid4().hex[:8]}", "test")
    await db_session.flush()
    perms = [await repo.get_or_create_permission(code, code.split(".")[0], code) for code in permissions]
    await repo.set_role_permissions(role, perms)
    await AuthorizationService(db_session).assign_role(user.id, role.id, organization.id, assigned_by_user_id=None)
    await db_session.flush()
    return {"Authorization": f"Bearer {tok}"}


async def find(client, headers, token, **params):
    response = await client.get(f"{BASE}/files", params={"q": token, "page_size": 200, **params}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


# ---- the registry matches the real schema ---------------------------------------------------------------------

async def test_every_registered_source_can_be_queried(client, auth_headers):
    response = await client.get(f"{BASE}/files", params={"page_size": 5}, headers=auth_headers)
    assert response.status_code == 200, response.text   # a wrong table or column name would fail here


async def test_usage_and_server_inspector_work_for_a_superuser(client, auth_headers):
    usage = await client.get(f"{BASE}/usage", headers=auth_headers)
    assert usage.status_code == 200, usage.text
    body = usage.json()
    assert body["scope"] == "platform" and body["can_delete"] is True
    assert {"total_bytes", "by_source", "by_type", "orphan_count", "duplicate_wasted_bytes"} <= set(body["files"])
    server = await client.get(f"{BASE}/server", headers=auth_headers)
    assert server.status_code == 200, server.text
    assert server.json()["database"]["total_bytes"] > 0 and server.json()["object_storage"]["bucket"] == settings.MINIO_BUCKET


# ---- browsing: records, orphans, folders, filters --------------------------------------------------------------

async def test_a_file_with_a_record_is_in_use_and_cannot_be_deleted(client, auth_headers, db_session, organization, store, token):
    key = f"{organization.id}/{token}/contract.pdf"
    await put(store, key, b"%PDF-1.4 synthetic", "application/pdf")
    db_session.add(Document(organization_id=organization.id, entity_type="test", filename="contract.pdf",
                            content_type="application/pdf", size_bytes=18, storage_key=key, status="uploaded"))
    await db_session.flush()

    (item,) = await find(client, auth_headers, token)
    assert item["status"] == "in_use" and item["source"] == "documents" and item["previewable"] == "pdf"
    assert item["organization_name"] == organization.name

    analysis = (await client.get(f"{BASE}/analysis", params={"id": item["id"]}, headers=auth_headers)).json()
    assert analysis["verdict"] == "in_use" and analysis["can_delete"] is False
    assert analysis["evidence"][0]["kind"] == "record"

    attempt = await client.post(f"{BASE}/deletions", headers=auth_headers,
                                json={"ids": [item["id"]], "reason": "should not work", "confirm_text": "DELETE 1"})
    assert attempt.status_code == 409
    assert await store.exists(key)   # nothing moved


async def test_a_database_record_whose_file_is_missing_is_flagged(client, auth_headers, db_session, organization, token):
    db_session.add(Document(organization_id=organization.id, entity_type="test", filename=f"{token}.pdf",
                            content_type="application/pdf", size_bytes=5, storage_key=f"{organization.id}/{token}/gone.pdf",
                            status="uploaded"))
    await db_session.flush()
    (item,) = await find(client, auth_headers, token)
    assert item["status"] == "missing_object"


async def test_folders_search_sort_and_filters(client, auth_headers, db_session, organization, store, token):
    await put(store, f"{organization.id}/{token}/a/small.txt", b"x")
    await put(store, f"{organization.id}/{token}/a/big.bin", b"y" * 5000, "application/octet-stream")
    await put(store, f"{organization.id}/{token}/b/other.txt", b"zz")

    folder = ["Object storage", "Unreferenced files", organization.name, token]
    response = await client.get(f"{BASE}/files", params={"path": "/".join(folder)}, headers=auth_headers)
    body = response.json()
    assert [f["name"] for f in body["folders"]] == ["a", "b"] and body["items"] == []
    assert {f["name"]: f["file_count"] for f in body["folders"]} == {"a": 2, "b": 1}

    inside = (await client.get(f"{BASE}/files", params={"path": "/".join([*folder, "a"]), "sort": "size", "order": "desc"},
                               headers=auth_headers)).json()
    assert [i["name"] for i in inside["items"]] == ["big.bin", "small.txt"]

    assert [i["name"] for i in await find(client, auth_headers, token, min_size=1000)] == ["big.bin"]
    assert {i["name"] for i in await find(client, auth_headers, token, type_group="text")} == {"small.txt", "other.txt"}
    assert {i["status"] for i in await find(client, auth_headers, token)} == {"orphan"}


async def test_duplicates_are_grouped_and_counted(client, auth_headers, organization, store, token):
    same = b"identical content " * 20
    await put(store, f"{organization.id}/{token}/one.txt", same)
    await put(store, f"{organization.id}/{token}/two.txt", same)
    await put(store, f"{organization.id}/{token}/three.txt", b"different")
    groups = (await client.get(f"{BASE}/duplicates", headers=auth_headers)).json()
    mine = [g for g in groups if any(token in f["location"] for f in g["files"])]
    assert len(mine) == 1 and mine[0]["count"] == 2 and mine[0]["wasted_bytes"] == len(same)


# ---- protected files -------------------------------------------------------------------------------------------

async def test_backups_are_protected_and_survive_a_delete_attempt(client, auth_headers, store, token):
    key = f"backups/{token}.dump"
    await put(store, key, b"PGDMP synthetic")
    (item,) = await find(client, auth_headers, token)
    assert item["status"] == "protected" and item["protected"] is True
    analysis = (await client.get(f"{BASE}/analysis", params={"id": item["id"]}, headers=auth_headers)).json()
    assert analysis["verdict"] == "protected" and analysis["can_delete"] is False
    attempt = await client.post(f"{BASE}/deletions", headers=auth_headers,
                                json={"ids": [item["id"]], "reason": "no way", "confirm_text": "DELETE 1"})
    assert attempt.status_code == 409 and await store.exists(key)


async def test_files_kept_inside_the_database_are_protected_but_can_be_previewed(client, auth_headers, db_session, organization):
    unique = uuid.uuid4().hex[:8]
    db_session.add(Institution(organization_id=organization.id, name=f"Inst {unique}", location="X", faculty_name="F",
                               mou_filename=f"mou-{unique}.pdf", mou_content_type="application/pdf",
                               mou_size_bytes=14, mou_data=b"%PDF-1.4 mou!!"))
    await db_session.flush()
    (item,) = await find(client, auth_headers, f"mou-{unique}")
    assert item["backend"] == "database" and item["protected"] is True and item["source"] == "institution_mous"

    attempt = await client.post(f"{BASE}/deletions", headers=auth_headers,
                                json={"ids": [item["id"]], "reason": "no way", "confirm_text": "DELETE 1"})
    assert attempt.status_code == 409

    preview = (await client.get(f"{BASE}/preview", params={"id": item["id"]}, headers=auth_headers)).json()
    assert preview["mode"] == "content" and preview["kind"] == "pdf"
    content = await client.get(preview["url"], headers=auth_headers)
    assert content.status_code == 200 and content.content == b"%PDF-1.4 mou!!"
    assert "sandbox" in content.headers["content-security-policy"] and content.headers["x-content-type-options"] == "nosniff"
    assert content.headers["content-disposition"].startswith("inline")


async def test_a_reference_in_a_table_the_registry_does_not_know_blocks_deletion(client, auth_headers, db_session, organization, store, token):
    key = f"{organization.id}/{token}/avatar.png"
    await put(store, key, b"png", "image/png")
    # user_profiles.avatar_url is not a registered source, but it can point at a stored file
    await db_session.execute(text("update user_profiles set avatar_url = :u where organization_id = :o"),
                             {"u": f"https://files.example/{key}", "o": organization.id})
    (item,) = await find(client, auth_headers, token)
    analysis = (await client.get(f"{BASE}/analysis", params={"id": item["id"]}, headers=auth_headers)).json()
    assert analysis["verdict"] == "in_use" and analysis["can_delete"] is False
    assert any("user_profiles.avatar_url" in e["text"] for e in analysis["evidence"])


# ---- preview and download --------------------------------------------------------------------------------------

async def test_object_storage_previews_use_short_lived_links_and_unsafe_types_download(client, auth_headers, organization, store, token):
    await put(store, f"{organization.id}/{token}/pic.png", b"png", "image/png")
    await put(store, f"{organization.id}/{token}/page.html", b"<script>alert(1)</script>", "text/html")
    images = {i["name"]: i for i in await find(client, auth_headers, token)}

    png = (await client.get(f"{BASE}/preview", params={"id": images["pic.png"]["id"]}, headers=auth_headers)).json()
    assert png["mode"] == "url" and png["kind"] == "image" and png["expires_in"] == 300
    assert "response-content-disposition=inline" in png["url"]

    html = (await client.get(f"{BASE}/preview", params={"id": images["page.html"]["id"]}, headers=auth_headers)).json()
    assert html["kind"] is None and "response-content-disposition=attachment" in html["url"]   # never rendered inline

    download = (await client.get(f"{BASE}/preview", params={"id": images["pic.png"]["id"], "download": "true"},
                                 headers=auth_headers)).json()
    assert "response-content-disposition=attachment" in download["url"]


# ---- trash, restore, purge, audit ------------------------------------------------------------------------------

async def test_delete_goes_to_trash_and_can_be_restored(client, auth_headers, organization, store, token):
    key = f"{organization.id}/{token}/old-export.csv"
    await put(store, key, b"a,b\n1,2\n", "text/csv")
    (item,) = await find(client, auth_headers, token)
    assert item["status"] == "orphan"

    preview = (await client.post(f"{BASE}/deletions/preview", headers=auth_headers, json={"ids": [item["id"]]})).json()
    assert preview["eligible_count"] == 1 and preview["blocked_count"] == 0 and preview["confirm_text"] == "DELETE 1"
    assert preview["items"][0]["verdict"] == "eligible"

    wrong = await client.post(f"{BASE}/deletions", headers=auth_headers,
                              json={"ids": [item["id"]], "reason": "cleanup", "confirm_text": "yes"})
    assert wrong.status_code in (400, 422) and await store.exists(key)

    done = await client.post(f"{BASE}/deletions", headers=auth_headers,
                             json={"ids": [item["id"]], "reason": "old export nobody uses", "confirm_text": "DELETE 1"})
    assert done.status_code == 200, done.text
    moved = done.json()["moved"][0]
    assert not await store.exists(key)                         # gone from its place...
    assert any(k.startswith(registry.TRASH_PREFIX) and k.endswith(key) for k in await store.list_all())   # ...and in .trash/
    trash = (await client.get(f"{BASE}/trash", headers=auth_headers)).json()
    entry = next(t for t in trash["items"] if t["id"] == moved["id"])
    assert entry["original_key"] == key and entry["reason"] == "old export nobody uses" and trash["min_days"] == 30
    assert entry["can_purge"] is False                         # not before 30 days
    assert not any(i["id"] == item["id"] for i in await find(client, auth_headers, token))   # not listed as a file now

    restored = await client.post(f"{BASE}/trash/{moved['id']}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    assert await store.exists(key) and restored.json()["restored_at"] is not None

    log = (await client.get(f"{BASE}/deletion-log", headers=auth_headers)).json()["items"]
    mine = [row for row in log if row["object_key"] == key]
    assert {row["action"] for row in mine} == {"trash", "restore"}
    trashed = next(row for row in mine if row["action"] == "trash")
    assert trashed["reason"] == "old export nobody uses" and trashed["evidence"][0]["kind"] == "note" and trashed["user_email"]


async def test_restore_refuses_to_overwrite_a_file_that_reappeared(client, auth_headers, organization, store, token):
    key = f"{organization.id}/{token}/again.txt"
    await put(store, key, b"first")
    (item,) = await find(client, auth_headers, token)
    moved = (await client.post(f"{BASE}/deletions", headers=auth_headers,
                               json={"ids": [item["id"]], "reason": "temporary", "confirm_text": "DELETE 1"})).json()["moved"][0]
    await put(store, key, b"second")
    again = await client.post(f"{BASE}/trash/{moved['id']}/restore", headers=auth_headers)
    assert again.status_code == 409
    assert (await store.read(key)) == b"second"


async def test_one_blocked_file_stops_the_whole_deletion(client, auth_headers, organization, store, token):
    free = f"{organization.id}/{token}/free.txt"
    kept = f"backups/{token}-keep.dump"
    await put(store, free, b"free")
    await put(store, kept, b"PGDMP")
    ids = {i["name"]: i["id"] for i in await find(client, auth_headers, token)}
    response = await client.post(f"{BASE}/deletions", headers=auth_headers,
                                 json={"ids": list(ids.values()), "reason": "mixed selection", "confirm_text": "DELETE 2"})
    assert response.status_code == 409 and await store.exists(free) and await store.exists(kept)


async def test_purge_is_blocked_inside_the_minimum_period_and_works_after(client, auth_headers, db_session, organization, store, token, monkeypatch):
    key = f"{organization.id}/{token}/purge-me.txt"
    await put(store, key, b"bye")
    (item,) = await find(client, auth_headers, token)
    moved = (await client.post(f"{BASE}/deletions", headers=auth_headers,
                               json={"ids": [item["id"]], "reason": "test purge", "confirm_text": "DELETE 1"})).json()["moved"][0]
    early = await client.post(f"{BASE}/trash/purge", headers=auth_headers,
                              json={"ids": [moved["id"]], "confirm_text": "PURGE 1"})
    assert early.status_code == 409 and "30 days" in early.text

    await db_session.execute(text("update storage_trash set deleted_at = :d where id = :i"),
                             {"d": datetime.now(timezone.utc) - timedelta(days=31), "i": moved["id"]})
    wrong = await client.post(f"{BASE}/trash/purge", headers=auth_headers, json={"ids": [moved["id"]], "confirm_text": "purge"})
    assert wrong.status_code in (400, 422)
    done = await client.post(f"{BASE}/trash/purge", headers=auth_headers, json={"ids": [moved["id"]], "confirm_text": "PURGE 1"})
    assert done.status_code == 200, done.text
    assert done.json()[0]["purged_at"] is not None
    trash_keys = [k for k in await store.list_all() if token in k]
    assert trash_keys == []                                    # the trash copy is gone too
    assert any(r["action"] == "purge" and r["object_key"] == key
               for r in (await client.get(f"{BASE}/deletion-log", headers=auth_headers)).json()["items"])


async def test_nothing_in_the_app_purges_automatically():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "modules" / "storage_manager"
    assert not (root / "tasks.py").exists()
    assert "celery" not in (root / "service.py").read_text().lower()


# ---- access control and organization isolation -----------------------------------------------------------------

async def test_an_administrator_sees_only_their_own_organization(client, db_session, organization, store, token):
    other = await OrganizationRepository(db_session).create(name=f"Other {token}", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    await put(store, f"{organization.id}/{token}/mine.txt")
    await put(store, f"{other.id}/{token}/theirs.txt")
    await put(store, f"{token}-no-org.txt")                    # belongs to no organization
    headers = await admin_headers(db_session, organization)

    names = {i["name"] for i in await find(client, headers, token)}
    assert names == {"mine.txt"}


async def test_an_administrator_can_inspect_but_not_delete_or_see_the_server(client, auth_headers, db_session, organization, store, token):
    key = f"{organization.id}/{token}/admin-view.txt"
    await put(store, key)
    headers = await admin_headers(db_session, organization)
    (item,) = await find(client, headers, token)

    analysis = (await client.get(f"{BASE}/analysis", params={"id": item["id"]}, headers=headers)).json()
    assert analysis["verdict"] == "eligible" and analysis["can_delete"] is False
    assert "superusers" in " ".join(analysis["reasons"])

    assert (await client.post(f"{BASE}/deletions", headers=headers,
                              json={"ids": [item["id"]], "reason": "try", "confirm_text": "DELETE 1"})).status_code == 403
    assert (await client.post(f"{BASE}/trash/purge", headers=headers,
                              json={"ids": [str(uuid.uuid4())], "confirm_text": "PURGE 1"})).status_code == 403
    assert (await client.get(f"{BASE}/server", headers=headers)).status_code == 403
    assert (await client.get(f"{BASE}/usage", headers=headers)).json()["scope"] == "organization"
    assert await store.exists(key)


async def test_another_organizations_file_cannot_be_opened_by_id(client, db_session, organization, store, token):
    other = await OrganizationRepository(db_session).create(name=f"Other {token}", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    key = f"{other.id}/{token}/secret.txt"
    await put(store, key)
    headers = await admin_headers(db_session, organization)
    file_id = encode_orphan_id(key)
    assert (await client.get(f"{BASE}/analysis", params={"id": file_id}, headers=headers)).status_code == 404
    assert (await client.get(f"{BASE}/preview", params={"id": file_id}, headers=headers)).status_code == 404


async def test_users_without_the_permission_are_refused(client, staff_headers):
    for path in ("/files", "/usage", "/trash", "/deletion-log", "/duplicates"):
        assert (await client.get(f"{BASE}{path}", headers=staff_headers)).status_code == 403


async def test_the_administrator_role_gets_the_view_permission_and_never_a_delete_permission(rbac_seeded, db_session):
    from modules.authorization.service import DEFAULT_PERMISSIONS

    codes = {p[0] for p in DEFAULT_PERMISSIONS if p[1] == "storage"}
    assert codes == {"storage.view"}                           # deletion is superuser-only, not a grantable permission


def test_orphan_ids_round_trip():
    key = "49f26b09-1d9f-40f6-b916-41f64a8f4949/social/ü ñ file (1).png"
    assert decode_orphan_id(encode_orphan_id(key)) == key
