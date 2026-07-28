import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.models import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Document:
        document = Document(**fields)
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def get_by_id(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> Document | None:
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id, Document.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_entity(
        self, organization_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
    ) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .where(
                Document.organization_id == organization_id,
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
                Document.status == DocumentStatus.UPLOADED,
            )
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_uploaded(self, document: Document, size_bytes: int) -> Document:
        document.status = DocumentStatus.UPLOADED
        document.size_bytes = size_bytes
        document.confirmed_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def delete(self, document: Document) -> None:
        await self.db.delete(document)
        await self.db.flush()
