import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.messaging.schemas import (
    AdminConversationListResponse,
    AdminConversationPublic,
    AttachmentUploadRequest,
    AttachmentUploadResponse,
    ConversationListResponse,
    ConversationPublic,
    MessagePublic,
    MessageResponse,
    OpenConversationResponse,
    SendMessageRequest,
    StudentContactPublic,
    TrainerContactPublic,
    UnreadCountResponse,
)
from modules.messaging.service import MessagingService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.trainers.dependencies import get_current_trainer
from modules.trainers.models import Trainer
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


def _to_conversation_public(row: dict) -> ConversationPublic:
    conversation = row["conversation"]
    return ConversationPublic(
        id=conversation.id,
        student_id=conversation.student_id,
        trainer_id=conversation.trainer_id,
        counterpart_name=row["counterpart_name"],
        last_message=MessagePublic.model_validate(row["last_message"]) if row["last_message"] else None,
        unread_count=row["unread_count"],
        created_at=conversation.created_at,
    )


# ---- Student self-service ----
#
# Ownership-gated via get_current_student, no permission code -- same
# "owning the record is the authorization" convention as every other
# student /me endpoint (modules/live_classes, modules/lms/*).


@router.get("/me/trainers", response_model=list[TrainerContactPublic])
async def list_my_trainers(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    rows = await service.get_trainers_for_student(student)
    return [TrainerContactPublic(trainer_id=t.id, full_name=name) for t, name in rows]


@router.get("/me/conversations", response_model=ConversationListResponse)
async def list_my_conversations(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    rows = await service.list_conversations_for_student(student)
    return ConversationListResponse(items=[_to_conversation_public(r) for r in rows])


@router.get("/me/conversations/unread-count", response_model=UnreadCountResponse)
async def get_my_unread_count(
    student: Student = Depends(get_current_student),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    count = await service.get_unread_count_for_student(student, user.id)
    return UnreadCountResponse(unread_count=count)


@router.post("/me/conversations/with/{trainer_id}", response_model=OpenConversationResponse)
async def open_conversation_with_trainer(
    trainer_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conversation = await service.open_conversation_as_student(student, trainer_id)
    return OpenConversationResponse(
        id=conversation.id, student_id=conversation.student_id, trainer_id=conversation.trainer_id
    )


@router.get("/me/conversations/{conversation_id}/messages", response_model=list[MessagePublic])
async def list_my_conversation_messages(
    conversation_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conversation = await service.get_conversation_for_student(conversation_id, student)
    messages = await service.list_messages(conversation, user.id)
    return [MessagePublic.model_validate(m) for m in messages]


@router.post("/me/conversations/{conversation_id}/messages", response_model=MessagePublic)
async def send_message_as_student(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    student: Student = Depends(get_current_student),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conversation = await service.get_sendable_conversation_for_student(conversation_id, student)
    message = await service.send_message(conversation, user.id, payload.body, payload.attachment_document_id)
    return MessagePublic.model_validate(message)


@router.post("/me/attachments/presigned-upload", response_model=AttachmentUploadResponse)
async def request_attachment_upload_as_student(
    payload: AttachmentUploadRequest,
    student: Student = Depends(get_current_student),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    document_id, upload_url = await service.request_attachment_upload(
        student.organization_id, user.id, student.id, payload.filename, payload.content_type
    )
    return AttachmentUploadResponse(document_id=document_id, upload_url=upload_url)


@router.post("/me/attachments/{document_id}/confirm", response_model=MessageResponse)
async def confirm_attachment_upload_as_student(
    document_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    await service.confirm_attachment_upload(document_id, student.organization_id)
    return MessageResponse(message="Attachment uploaded successfully.")


# ---- Trainer self-service ----


@router.get("/trainer/me/students", response_model=list[StudentContactPublic])
async def list_my_students(
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    students = await service.get_students_for_trainer(trainer)
    return [StudentContactPublic(student_id=s.id, full_name=s.full_name) for s in students]


@router.get("/trainer/me/conversations", response_model=ConversationListResponse)
async def list_my_conversations_as_trainer(
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    rows = await service.list_conversations_for_trainer(trainer)
    return ConversationListResponse(items=[_to_conversation_public(r) for r in rows])


@router.get("/trainer/me/conversations/unread-count", response_model=UnreadCountResponse)
async def get_my_unread_count_as_trainer(
    trainer: Trainer = Depends(get_current_trainer),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    count = await service.get_unread_count_for_trainer(trainer, user.id)
    return UnreadCountResponse(unread_count=count)


@router.post("/trainer/me/conversations/with/{student_id}", response_model=OpenConversationResponse)
async def open_conversation_with_student(
    student_id: uuid.UUID,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conversation = await service.open_conversation_as_trainer(trainer, student_id)
    return OpenConversationResponse(
        id=conversation.id, student_id=conversation.student_id, trainer_id=conversation.trainer_id
    )


@router.get("/trainer/me/conversations/{conversation_id}/messages", response_model=list[MessagePublic])
async def list_my_conversation_messages_as_trainer(
    conversation_id: uuid.UUID,
    trainer: Trainer = Depends(get_current_trainer),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conversation = await service.get_conversation_for_trainer(conversation_id, trainer)
    messages = await service.list_messages(conversation, user.id)
    return [MessagePublic.model_validate(m) for m in messages]


@router.post("/trainer/me/conversations/{conversation_id}/messages", response_model=MessagePublic)
async def send_message_as_trainer(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    trainer: Trainer = Depends(get_current_trainer),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conversation = await service.get_sendable_conversation_for_trainer(conversation_id, trainer)
    message = await service.send_message(conversation, user.id, payload.body, payload.attachment_document_id)
    return MessagePublic.model_validate(message)


@router.post("/trainer/me/attachments/presigned-upload", response_model=AttachmentUploadResponse)
async def request_attachment_upload_as_trainer(
    payload: AttachmentUploadRequest,
    trainer: Trainer = Depends(get_current_trainer),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    document_id, upload_url = await service.request_attachment_upload(
        trainer.organization_id, user.id, trainer.id, payload.filename, payload.content_type
    )
    return AttachmentUploadResponse(document_id=document_id, upload_url=upload_url)


@router.post("/trainer/me/attachments/{document_id}/confirm", response_model=MessageResponse)
async def confirm_attachment_upload_as_trainer(
    document_id: uuid.UUID,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    await service.confirm_attachment_upload(document_id, trainer.organization_id)
    return MessageResponse(message="Attachment uploaded successfully.")


# ---- Admin oversight (read-only, no send route) ----


@router.get("/conversations", response_model=AdminConversationListResponse)
async def list_conversations_for_admin(
    student_id: uuid.UUID | None = None,
    trainer_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("messaging.view_all")),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    rows, total = await service.list_conversations_for_admin(
        organization_id, student_id=student_id, trainer_id=trainer_id, skip=skip, limit=limit
    )
    items = [
        AdminConversationPublic(
            id=r["conversation"].id,
            student_id=r["conversation"].student_id,
            student_name=r["student_name"],
            trainer_id=r["conversation"].trainer_id,
            trainer_name=r["trainer_name"],
            last_message=MessagePublic.model_validate(r["last_message"]) if r["last_message"] else None,
            created_at=r["conversation"].created_at,
        )
        for r in rows
    ]
    return AdminConversationListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessagePublic])
async def list_conversation_messages_for_admin(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("messaging.view_all")),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    messages = await service.list_messages_for_admin(conversation_id, organization_id)
    return [MessagePublic.model_validate(m) for m in messages]
