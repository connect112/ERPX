"""
Browsers can't reach object storage at its internal address (minio:9000), so presigned URLs can be returned as a path on
the site the user is on (STORAGE_PUBLIC_PREFIX). The web server forwards that path to storage; these tests check the
rewrite leaves everything the signature covers untouched, against a real storage server.
"""

import uuid
from urllib.parse import urlsplit

import httpx
import pytest

from app.core.config import settings
from packages.storage.client import StorageClient, public_url

pytestmark = pytest.mark.api


def test_without_a_prefix_the_url_is_left_alone(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_PREFIX", "")
    url = f"http://{settings.MINIO_ENDPOINT}/bucket/key?X-Amz-Signature=abc"
    assert public_url(url) == url


@pytest.mark.parametrize("prefix", ["/_files", "/_files/", " /_files "])
def test_the_internal_address_is_replaced_by_the_prefix(monkeypatch, prefix):
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_PREFIX", prefix)
    url = f"http://{settings.MINIO_ENDPOINT}/bucket/some%20key.pdf?X-Amz-Algorithm=AWS4&X-Amz-Signature=abc"
    assert public_url(url) == "/_files/bucket/some%20key.pdf?X-Amz-Algorithm=AWS4&X-Amz-Signature=abc"
    assert public_url("https://elsewhere.example/bucket/key") == "https://elsewhere.example/bucket/key"  # not ours


async def test_a_browser_upload_through_the_prefix_reaches_storage_and_can_be_downloaded(monkeypatch):
    """What the web server does: take the path after the prefix, call storage with the Host it was signed for."""
    storage = StorageClient()
    await storage.ensure_bucket()
    key = f"tests/{uuid.uuid4().hex}/receipt.pdf"
    monkeypatch.setattr(settings, "STORAGE_PUBLIC_PREFIX", "/_files")

    upload = storage.presigned_upload_url(key, "application/pdf")
    assert upload.startswith("/_files/") and "minio:9000" not in upload
    host = settings.MINIO_ENDPOINT
    forwarded = upload[len("/_files") :]  # handle_path strips the prefix
    async with httpx.AsyncClient(base_url=f"http://{host}") as http:
        put = await http.put(forwarded, content=b"%PDF-1.4 receipt", headers={"Host": host, "Content-Type": "application/pdf"})
        assert put.status_code == 200, put.text
        assert await storage.object_exists(key)
        download = storage.presigned_download_url(key)
        assert download.startswith("/_files/")
        got = await http.get(download[len("/_files") :], headers={"Host": host})
        assert got.status_code == 200 and got.content == b"%PDF-1.4 receipt"
        # A URL that wasn't signed by us is refused by storage itself, so the public path exposes nothing else.
        parts = urlsplit(forwarded)
        forged = await http.get(parts.path + "?X-Amz-Signature=forged", headers={"Host": host})
        assert forged.status_code in (400, 403)
    await storage.delete_object(key)
