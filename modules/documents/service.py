import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.documents.models import Document, DocumentStatus
from modules.documents.repository import DocumentRepository
from packages.storage.client import get_storage_client

logger = get_logger(__name__)

# Deliberately conservative — this is a generic attachment endpoint used by
# every module, so the cap has to be safe for the least trusted caller, not
# tuned per use case. Modules needing larger uploads (e.g. video lessons)
# should get a dedicated, purpose-specific limit when that's built.
MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DocumentRepository(db)
        self.storage = get_storage_client()

    async def request_upload(
        self,
        organization_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID | None,
        filename: str,
        content_type: str,
    ) -> tuple[Document, str]:
        await self.storage.ensure_bucket()

        object_key = f"{organization_id}/{entity_type}/{entity_id or 'unattached'}/{uuid.uuid4()}-{filename}"
        document = await self.repo.create(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            filename=filename,
            content_type=content_type,
            storage_key=object_key,
            status=DocumentStatus.PENDING,
        )
        upload_url = self.storage.presigned_upload_url(object_key, content_type)
        logger.info("document_upload_requested", document_id=str(document.id), entity_type=entity_type)
        return document, upload_url

    async def confirm_upload(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> Document:
        document = await self.repo.get_by_id(document_id, organization_id)
        if not document:
            raise NotFoundError("Document", document_id)
        if document.status == DocumentStatus.UPLOADED:
            return document

        exists = await self.storage.object_exists(document.storage_key)
        if not exists:
            raise ValidationError(
                "The file was not found in storage. Retry the upload before confirming."
            )

        # Read the real size back from storage rather than trusting a
        # client-supplied value — that's what keeps `size_bytes` trustworthy
        # for quota/reporting purposes, and lets us enforce the size cap
        # even though the API never saw the bytes stream through it.
        size_bytes = await self.storage.object_size(document.storage_key)
        if size_bytes > MAX_UPLOAD_SIZE_BYTES:
            await self.storage.delete_object(document.storage_key)
            await self.repo.delete(document)
            raise ValidationError(
                f"File exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB upload limit."
            )

        document = await self.repo.mark_uploaded(document, size_bytes=size_bytes)
        logger.info("document_upload_confirmed", document_id=str(document.id))
        return document

    async def list_for_entity(
        self, organization_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
    ) -> list[Document]:
        return await self.repo.list_for_entity(organization_id, entity_type, entity_id)

    async def get_download_url(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> str:
        document = await self.repo.get_by_id(document_id, organization_id)
        if not document or document.status != DocumentStatus.UPLOADED:
            raise NotFoundError("Document", document_id)
        return self.storage.presigned_download_url(document.storage_key)

    async def delete_document(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        document = await self.repo.get_by_id(document_id, organization_id)
        if not document:
            raise NotFoundError("Document", document_id)
        if document.status == DocumentStatus.UPLOADED:
            await self.storage.delete_object(document.storage_key)
        await self.repo.delete(document)
        logger.info("document_deleted", document_id=str(document_id))
