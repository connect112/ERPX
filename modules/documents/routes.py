import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.documents.schemas import (
    DocumentDownloadResponse,
    DocumentPublic,
    DocumentUploadRequest,
    DocumentUploadResponse,
    MessageResponse,
)
from modules.documents.service import DocumentService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("/presigned-upload", response_model=DocumentUploadResponse)
async def request_upload(
    payload: DocumentUploadRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("documents.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    document, upload_url = await service.request_upload(
        organization_id,
        uploaded_by_user_id=user.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        filename=payload.filename,
        content_type=payload.content_type,
    )
    return DocumentUploadResponse(document_id=document.id, upload_url=upload_url)


@router.post("/{document_id}/confirm", response_model=DocumentPublic)
async def confirm_upload(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("documents.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    document = await service.confirm_upload(document_id, organization_id)
    return DocumentPublic.model_validate(document)


@router.get("", response_model=list[DocumentPublic])
async def list_documents(
    entity_type: str,
    entity_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("documents.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    documents = await service.list_for_entity(organization_id, entity_type, entity_id)
    return [DocumentPublic.model_validate(d) for d in documents]


@router.get("/{document_id}/download-url", response_model=DocumentDownloadResponse)
async def get_download_url(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("documents.view")),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    url = await service.get_download_url(document_id, organization_id)
    return DocumentDownloadResponse(download_url=url)


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("documents.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    await service.delete_document(document_id, organization_id)
    return MessageResponse(message="Document deleted successfully.")
