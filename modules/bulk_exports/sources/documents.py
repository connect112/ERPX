"""
Files uploaded through the Documents module (contracts, HR records, course resources, ...), copied from object storage
exactly as they were uploaded. Each file keeps its own extension. Needs ``documents.view``, like the single download.

The scope is the whole organization, or one record's files when a scope id (the record's id) is given; the status filter
is the kind of record (``entity_type``).
"""

import uuid
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.bulk_exports.sources.base import DocumentSource, ExportItem, FilterOption, Placeholder, Scope, matches
from modules.documents.models import Document, DocumentStatus

PERMISSION = "documents.view"
MAX_FILE_BYTES = 100 * 1024 * 1024

_PLACEHOLDERS = (
    Placeholder("original_name", "Original file name (without extension)", "offer-scan"),
    Placeholder("record_type", "Record type", "corporate_clients"),
    Placeholder("uploaded_date", "Uploaded on", "2026-10-30"),
    Placeholder("document_id", "Document ID", "3f2a9c1e"),
)


def _split(filename: str) -> tuple[str, str]:
    path = PurePosixPath(filename.replace("\\", "/")).name
    stem, dot, ext = path.rpartition(".")
    if not dot or not stem:
        return path, ""
    return stem, ext.lower()


class DocumentsSource(DocumentSource):
    key = "documents"
    label = "Uploaded documents"
    module = "documents"
    document_type = "Document"
    scope_kind = None
    extension = None
    base_placeholders = _PLACEHOLDERS
    presets = (
        ("Original file name", "{{original_name}}"),
        ("Record type, original name", "{{record_type}}_{{original_name}}"),
    )
    folder_presets = (("By record type", "{{record_type}}"),)

    async def open_scope(self, db: AsyncSession, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None) -> Scope:
        if not user.is_superuser and PERMISSION not in await AuthorizationRepository(db).get_permission_codes_for_user(user.id):
            raise AuthorizationError(f"This action requires the following permission(s): {PERMISSION}")
        types = (
            await db.execute(
                select(Document.entity_type)
                .where(Document.organization_id == organization_id, Document.status == DocumentStatus.UPLOADED)
                .distinct()
                .order_by(Document.entity_type)
            )
        ).scalars().all()
        return Scope(
            id=scope_id,
            label="Documents",
            organization_id=organization_id,
            extra={"types": [FilterOption(t, t.replace("_", " ").capitalize()) for t in types]},
        )

    async def query(self, db: AsyncSession, scope: Scope, search: str | None, status: str | None) -> list[ExportItem]:
        query = (
            select(Document)
            .where(Document.organization_id == scope.organization_id, Document.status == DocumentStatus.UPLOADED)
            .order_by(Document.entity_type, Document.filename, Document.id)
        )
        if scope.id is not None:
            query = query.where(Document.entity_id == scope.id)
        if status:
            query = query.where(Document.entity_type == status)
        items = []
        for doc in (await db.execute(query)).scalars():
            if not matches(search, doc.filename, doc.entity_type):
                continue
            stem, ext = _split(doc.filename)
            items.append(
                ExportItem(
                    id=doc.id,
                    title=doc.filename,
                    subtitle=doc.entity_type,
                    status=doc.entity_type,
                    values={
                        "original_name": stem,
                        "record_type": doc.entity_type,
                        "uploaded_date": (doc.confirmed_at or doc.created_at).date().isoformat(),
                        "document_id": doc.id.hex[:8],
                    },
                    extension=ext,
                    ref=doc,
                )
            )
        return items

    async def fetch(self, db: AsyncSession, scope: Scope, item: ExportItem) -> bytes:
        from packages.storage.client import get_storage_client

        doc: Document = item.ref
        if doc is None or doc.organization_id != scope.organization_id:
            raise NotFoundError("Document", item.id)
        return await get_storage_client().read_bytes(doc.storage_key, max_bytes=MAX_FILE_BYTES)
