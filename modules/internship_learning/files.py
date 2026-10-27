"""
Files attached to things in an internship (assignment material, student submissions, later project documents). The bytes
live in object storage (MinIO) and are handed back only as short-lived presigned links; the database keeps the record.
"""

import os
import re
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.internship_learning.models import InternshipFile
from packages.storage.client import get_storage_client

logger = get_logger(__name__)

MAX_FILE_BYTES = 25 * 1024 * 1024

# Programs that run on a student's or reviewer's machine; nobody should be handing these around through the portal.
BLOCKED_EXTENSIONS = {
    ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".pif", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".ps1", ".psm1", ".lnk", ".reg", ".dll", ".jar", ".hta", ".cpl", ".apk",
}  # fmt: skip


def safe_filename(name: str) -> str:
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = re.sub(r"[^A-Za-z0-9._ \-()]", "_", base).strip(" .")
    return (base or "file")[:150]


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage_client()

    @staticmethod
    def check_name(filename: str) -> str:
        clean = safe_filename(filename)
        if os.path.splitext(clean)[1].lower() in BLOCKED_EXTENSIONS:
            raise ValidationError(f"{clean}: this type of file cannot be uploaded.")
        return clean

    async def read_upload(self, upload: UploadFile) -> tuple[str, str, bytes]:
        """Validate one upload and return (filename, content type, bytes). Nothing is stored yet, so a batch can be
        checked as a whole before any of it is kept."""
        filename = self.check_name(upload.filename or "")
        data = await upload.read(MAX_FILE_BYTES + 1)
        if not data:
            raise ValidationError(f"{filename} is empty.")
        if len(data) > MAX_FILE_BYTES:
            raise ValidationError(f"{filename} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
        return filename, (upload.content_type or "application/octet-stream")[:150], data

    async def store(
        self,
        *,
        organization_id: uuid.UUID,
        internship_id: uuid.UUID,
        owner_type: str,
        owner_id: uuid.UUID,
        uploaded_by: uuid.UUID | None,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> InternshipFile:
        await self.storage.ensure_bucket()
        key = f"internships/{internship_id}/{owner_type}/{owner_id}/{uuid.uuid4().hex}-{filename}"
        await self.storage.upload_bytes(key, data, content_type)
        record = InternshipFile(
            organization_id=organization_id,
            internship_id=internship_id,
            owner_type=owner_type,
            owner_id=owner_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            object_key=key,
            uploaded_by_user_id=uploaded_by,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def for_owners(self, owner_type: str, owner_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[InternshipFile]]:
        if not owner_ids:
            return {}
        rows = await self.db.execute(
            select(InternshipFile)
            .where(InternshipFile.owner_type == owner_type, InternshipFile.owner_id.in_(owner_ids))
            .order_by(InternshipFile.created_at)
        )
        grouped: dict[uuid.UUID, list[InternshipFile]] = {}
        for record in rows.scalars().all():
            grouped.setdefault(record.owner_id, []).append(record)
        return grouped

    async def get(self, file_id: uuid.UUID, owner_type: str, owner_id: uuid.UUID) -> InternshipFile:
        record = (
            await self.db.execute(
                select(InternshipFile).where(
                    InternshipFile.id == file_id,
                    InternshipFile.owner_type == owner_type,
                    InternshipFile.owner_id == owner_id,
                )
            )
        ).scalar_one_or_none()
        if not record:
            raise NotFoundError("File", file_id)
        return record

    def download_url(self, record: InternshipFile) -> str:
        return self.storage.presigned_download_url(record.object_key)

    async def delete(self, record: InternshipFile) -> None:
        """Forget the record first and take the stored bytes away best-effort: a leftover object is harmless, a record
        pointing at nothing is not."""
        key = record.object_key
        await self.db.delete(record)
        await self.db.flush()
        try:
            await self.storage.delete_object(key)
        except Exception:  # noqa: BLE001 - storage hiccup must not undo the delete
            logger.warning("internship_file_object_delete_failed", object_key=key, exc_info=True)

    async def delete_all(self, owner_type: str, owner_id: uuid.UUID) -> None:
        for record in (await self.for_owners(owner_type, [owner_id])).get(owner_id, []):
            await self.delete(record)
