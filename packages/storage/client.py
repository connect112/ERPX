"""
Shared object-storage package.

Every module that needs to store an uploaded file (Documents, Course
Resources, user avatars, corporate contract attachments, ...) goes
through `get_storage_client()` rather than importing the MinIO SDK
directly, mirroring the same "one shared client, many callers" pattern
`packages.ai` and `packages.email` already use.

Real MinIO calls, not a stub — this hits the configured endpoint using
`settings.MINIO_*`, the same way `packages.ai` makes real HTTP calls to
an LLM provider. Uploads and downloads never proxy through the API
process: the API only ever hands out short-lived presigned URLs, and the
browser talks to MinIO directly. This is the standard pattern for object
storage at any scale — the API would otherwise become a bandwidth
bottleneck and a single point of failure for every file transfer.

The MinIO SDK is synchronous. `bucket_exists`/`make_bucket`/`remove_object`
perform real network I/O, so those are dispatched via `asyncio.to_thread`
to avoid blocking the event loop. Presigned URL generation is pure local
HMAC signing with no network call, so it's cheap enough to call directly.
"""

import asyncio
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_PRESIGN_EXPIRY = timedelta(minutes=15)
DOWNLOAD_PRESIGN_EXPIRY = timedelta(hours=1)


def public_url(url: str) -> str:
    """A presigned URL the browser can use. With STORAGE_PUBLIC_PREFIX set, the internal storage address is replaced
    by that prefix (a path on the site the user is on); the signed path and query are left exactly as they were."""
    prefix = settings.STORAGE_PUBLIC_PREFIX.strip().rstrip("/")
    if not prefix:
        return url
    internal = f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}"
    if not url.startswith(internal):
        return url
    return prefix + url[len(internal) :]


class StorageClient:
    def __init__(self) -> None:
        self._client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET

    async def ensure_bucket(self) -> None:
        try:
            exists = await asyncio.to_thread(self._client.bucket_exists, self.bucket)
            if not exists:
                await asyncio.to_thread(self._client.make_bucket, self.bucket)
                logger.info("storage_bucket_created", bucket=self.bucket)
        except S3Error as exc:
            logger.exception("storage_bucket_check_failed", bucket=self.bucket)
            raise ServiceUnavailableError("Could not reach object storage.") from exc

    def presigned_upload_url(self, object_key: str, content_type: str) -> str:
        try:
            return public_url(
                self._client.presigned_put_object(self.bucket, object_key, expires=DEFAULT_PRESIGN_EXPIRY)
            )
        except S3Error as exc:
            logger.exception("storage_presign_upload_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not generate an upload URL.") from exc

    def presigned_download_url(self, object_key: str) -> str:
        try:
            return public_url(
                self._client.presigned_get_object(self.bucket, object_key, expires=DOWNLOAD_PRESIGN_EXPIRY)
            )
        except S3Error as exc:
            logger.exception("storage_presign_download_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not generate a download URL.") from exc

    async def delete_object(self, object_key: str) -> None:
        try:
            await asyncio.to_thread(self._client.remove_object, self.bucket, object_key)
        except S3Error as exc:
            logger.exception("storage_delete_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not delete the stored file.") from exc

    async def object_exists(self, object_key: str) -> bool:
        try:
            await asyncio.to_thread(self._client.stat_object, self.bucket, object_key)
            return True
        except S3Error:
            return False

    async def object_size(self, object_key: str) -> int:
        try:
            stat = await asyncio.to_thread(self._client.stat_object, self.bucket, object_key)
            return stat.size
        except S3Error as exc:
            logger.exception("storage_stat_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not read file metadata from storage.") from exc

    async def upload_file(
        self, object_key: str, file_path: str, content_type: str = "application/octet-stream"
    ) -> None:
        """Server-side upload for files the API itself produces (e.g. a
        database dump) rather than a browser-uploaded file — those still go
        through `presigned_upload_url` so bytes never transit this process."""
        try:
            await asyncio.to_thread(
                self._client.fput_object, self.bucket, object_key, file_path, content_type=content_type
            )
        except S3Error as exc:
            logger.exception("storage_upload_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not upload the file to storage.") from exc

    async def upload_bytes(self, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Store small bytes the API itself made or checked (e.g. a rendered image or a validated upload)."""
        import io

        try:
            await asyncio.to_thread(
                self._client.put_object, self.bucket, object_key, io.BytesIO(data), len(data), content_type=content_type
            )
        except S3Error as exc:
            logger.exception("storage_upload_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not upload the file to storage.") from exc

    async def read_bytes(self, object_key: str, max_bytes: int = 20 * 1024 * 1024) -> bytes:
        """Read a small stored file into memory (refuses anything bigger than max_bytes)."""

        def _read() -> bytes:
            response = self._client.get_object(self.bucket, object_key)
            try:
                data = response.read(max_bytes + 1)
            finally:
                response.close()
                response.release_conn()
            return data

        try:
            data = await asyncio.to_thread(_read)
        except S3Error as exc:
            logger.exception("storage_read_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not read the file from storage.") from exc
        if len(data) > max_bytes:
            raise ServiceUnavailableError("The stored file is larger than expected.")
        return data

    async def download_file(self, object_key: str, dest_path: str) -> None:
        """Server-side download for callers that need the bytes on local
        disk rather than a presigned URL to hand to a browser — currently
        only apps/api/scripts/restore_backup.py, which needs a real file
        path to pass to `psql -f`."""
        try:
            await asyncio.to_thread(self._client.fget_object, self.bucket, object_key, dest_path)
        except S3Error as exc:
            logger.exception("storage_download_failed", object_key=object_key)
            raise ServiceUnavailableError("Could not download the file from storage.") from exc


_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    global _client
    if _client is None:
        _client = StorageClient()
    return _client
