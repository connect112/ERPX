"""
Messaging module — service layer.

Isolation has no separate membership table to check: "which trainer(s)
can this student message" and "which student(s) can this trainer
message" are derived live from Batch.trainer_id + BatchEnrollment on
every relevant call (see get_trainer_ids_for_student /
get_student_ids_for_trainer), exactly like modules/live_classes derives
its own ownership checks. A conversation's *history* stays readable even
if that derivation later excludes the pair (e.g. a trainer reassigned
off the batch) -- nothing here deletes past messages, only new sends
and new conversations are gated.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.documents.models import DocumentStatus
from modules.documents.repository import DocumentRepository
from modules.documents.service import DocumentService
from modules.employees.repository import EmployeeRepository
from modules.messaging.models import MessagingConversation, MessagingMessage
from modules.messaging.repository import ConversationRepository, MessageRepository
from modules.notifications.models import NotificationType
from modules.notifications.service import NotificationService
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.trainers.models import Trainer
from modules.trainers.repository import TrainerRepository

logger = get_logger(__name__)

# Stricter than modules/documents' generic 25MB cap (see DocumentService.
# confirm_upload's max_size_bytes param) -- chat attachments are photos and
# short videos, not arbitrary files, so they get their own dedicated ceiling.
MESSAGE_ATTACHMENT_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class MessagingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.message_repo = MessageRepository(db)
        self.document_repo = DocumentRepository(db)
        self.document_service = DocumentService(db)
        self.batch_repo = BatchRepository(db)
        self.batch_enrollment_repo = BatchEnrollmentRepository(db)
        self.student_repo = StudentRepository(db)
        self.trainer_repo = TrainerRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.notification_service = NotificationService(db)

    # ---- deriving who a student/trainer may talk to ----

    async def get_trainer_ids_for_student(
        self, student_id: uuid.UUID, organization_id: uuid.UUID
    ) -> set[uuid.UUID]:
        batch_ids = await self.batch_enrollment_repo.list_batch_ids_for_student(
            student_id, organization_id
        )
        batches = await self.batch_repo.list_for_ids(batch_ids, organization_id)
        return {b.trainer_id for b in batches if b.trainer_id}

    async def get_trainers_for_student(self, student: Student) -> list[tuple[Trainer, str]]:
        trainer_ids = await self.get_trainer_ids_for_student(student.id, student.organization_id)
        rows = await self.trainer_repo.list_with_employee_for_ids(
            list(trainer_ids), student.organization_id
        )
        return [(trainer, employee.full_name) for trainer, employee in rows]

    async def get_student_ids_for_trainer(
        self, trainer_id: uuid.UUID, organization_id: uuid.UUID
    ) -> set[uuid.UUID]:
        batches = await self.batch_repo.list_for_trainer(trainer_id, organization_id)
        batch_ids = [b.id for b in batches]
        students = await self.batch_enrollment_repo.list_students_for_batches(batch_ids, organization_id)
        return {s.id for s in students}

    async def get_students_for_trainer(self, trainer: Trainer) -> list[Student]:
        student_ids = await self.get_student_ids_for_trainer(trainer.id, trainer.organization_id)
        return await self.student_repo.list_for_ids(list(student_ids), trainer.organization_id)

    # ---- opening/reaching a conversation, ownership-checked ----

    async def open_conversation_as_student(self, student: Student, trainer_id: uuid.UUID) -> MessagingConversation:
        trainer_ids = await self.get_trainer_ids_for_student(student.id, student.organization_id)
        if trainer_id not in trainer_ids:
            raise NotFoundError("Trainer", trainer_id)
        return await self.conversation_repo.get_or_create(student.organization_id, student.id, trainer_id)

    async def open_conversation_as_trainer(self, trainer: Trainer, student_id: uuid.UUID) -> MessagingConversation:
        student_ids = await self.get_student_ids_for_trainer(trainer.id, trainer.organization_id)
        if student_id not in student_ids:
            raise NotFoundError("Student", student_id)
        return await self.conversation_repo.get_or_create(trainer.organization_id, student_id, trainer.id)

    async def get_conversation_for_student(self, conversation_id: uuid.UUID, student: Student) -> MessagingConversation:
        """Ownership only -- used for reading history, which stays visible
        even if the student-trainer pairing has since changed (e.g. the
        trainer was reassigned off the batch)."""
        conversation = await self.conversation_repo.get_by_id(conversation_id, student.organization_id)
        if not conversation or conversation.student_id != student.id:
            raise NotFoundError("MessagingConversation", conversation_id)
        return conversation

    async def get_conversation_for_trainer(self, conversation_id: uuid.UUID, trainer: Trainer) -> MessagingConversation:
        """Ownership only -- see get_conversation_for_student's docstring."""
        conversation = await self.conversation_repo.get_by_id(conversation_id, trainer.organization_id)
        if not conversation or conversation.trainer_id != trainer.id:
            raise NotFoundError("MessagingConversation", conversation_id)
        return conversation

    async def get_sendable_conversation_for_student(self, conversation_id: uuid.UUID, student: Student) -> MessagingConversation:
        """Ownership *and* a live re-check that this trainer is still one
        this student is actually paired with -- new sends are cut off by a
        batch reassignment even though the conversation's history isn't."""
        conversation = await self.get_conversation_for_student(conversation_id, student)
        trainer_ids = await self.get_trainer_ids_for_student(student.id, student.organization_id)
        if conversation.trainer_id not in trainer_ids:
            raise ValidationError("You can no longer send messages to this trainer.")
        return conversation

    async def get_sendable_conversation_for_trainer(self, conversation_id: uuid.UUID, trainer: Trainer) -> MessagingConversation:
        """See get_sendable_conversation_for_student's docstring."""
        conversation = await self.get_conversation_for_trainer(conversation_id, trainer)
        student_ids = await self.get_student_ids_for_trainer(trainer.id, trainer.organization_id)
        if conversation.student_id not in student_ids:
            raise ValidationError("You can no longer send messages to this student.")
        return conversation

    # ---- listing conversations, enriched with the counterpart's name ----

    async def list_conversations_for_student(self, student: Student) -> list[dict]:
        conversations = await self.conversation_repo.list_for_student(student.id, student.organization_id)
        trainer_ids = [c.trainer_id for c in conversations]
        rows = await self.trainer_repo.list_with_employee_for_ids(trainer_ids, student.organization_id)
        name_by_trainer_id = {t.id: e.full_name for t, e in rows}
        return [
            await self._enrich_conversation(c, name_by_trainer_id.get(c.trainer_id, "Unknown"), student.user_id)
            for c in conversations
        ]

    async def get_unread_count_for_student(self, student: Student, reader_user_id: uuid.UUID) -> int:
        conversations = await self.conversation_repo.list_for_student(student.id, student.organization_id)
        return await self.message_repo.unread_count_for_conversations(
            [c.id for c in conversations], reader_user_id
        )

    async def get_unread_count_for_trainer(self, trainer: Trainer, reader_user_id: uuid.UUID) -> int:
        conversations = await self.conversation_repo.list_for_trainer(trainer.id, trainer.organization_id)
        return await self.message_repo.unread_count_for_conversations(
            [c.id for c in conversations], reader_user_id
        )

    async def list_conversations_for_trainer(self, trainer: Trainer) -> list[dict]:
        conversations = await self.conversation_repo.list_for_trainer(trainer.id, trainer.organization_id)
        student_ids = [c.student_id for c in conversations]
        students = await self.student_repo.list_for_ids(student_ids, trainer.organization_id)
        name_by_student_id = {s.id: s.full_name for s in students}
        employee = await self.employee_repo.get_by_id(trainer.employee_id, trainer.organization_id)
        reader_user_id = employee.user_id if employee else None
        return [
            await self._enrich_conversation(c, name_by_student_id.get(c.student_id, "Unknown"), reader_user_id)
            for c in conversations
        ]

    async def _enrich_conversation(
        self, conversation: MessagingConversation, counterpart_name: str, reader_user_id: uuid.UUID | None
    ) -> dict:
        last_message = await self.message_repo.get_last_message(conversation.id)
        unread_count = (
            await self.message_repo.unread_count_for_conversations([conversation.id], reader_user_id)
            if reader_user_id
            else 0
        )
        return {
            "conversation": conversation,
            "counterpart_name": counterpart_name,
            "last_message": last_message,
            "unread_count": unread_count,
        }

    # ---- sending / reading messages ----

    async def send_message(
        self,
        conversation: MessagingConversation,
        sender_user_id: uuid.UUID,
        body: str | None,
        attachment_document_id: uuid.UUID | None,
    ) -> MessagingMessage:
        if not body and not attachment_document_id:
            raise ValidationError("A message needs text or an attachment.")

        if attachment_document_id is not None:
            document = await self.document_repo.get_by_id(attachment_document_id, conversation.organization_id)
            if not document or document.status != DocumentStatus.UPLOADED:
                raise ValidationError("This attachment hasn't finished uploading.")
            already_used = await self.message_repo.get_attachment_usage(attachment_document_id)
            if already_used:
                raise ValidationError("This attachment has already been sent in another message.")

        message = await self.message_repo.create(
            conversation_id=conversation.id,
            sender_user_id=sender_user_id,
            body=body,
            attachment_document_id=attachment_document_id,
        )

        recipient_user_id = await self._resolve_recipient_user_id(conversation, sender_user_id)
        if recipient_user_id is not None:
            preview = body[:120] if body else "Sent an attachment"
            await self.notification_service.create_notification(
                organization_id=conversation.organization_id,
                user_id=recipient_user_id,
                title="New message",
                body=preview,
                notification_type=NotificationType.INFO,
                link_url=f"/messaging/{conversation.id}",
                source="messaging",
            )
        logger.info("message_sent", conversation_id=str(conversation.id), message_id=str(message.id))
        return message

    async def _resolve_recipient_user_id(
        self, conversation: MessagingConversation, sender_user_id: uuid.UUID
    ) -> uuid.UUID | None:
        student = await self.student_repo.get_by_id(conversation.student_id, conversation.organization_id)
        student_user_id = student.user_id if student else None
        if student_user_id != sender_user_id:
            return student_user_id
        trainer = await self.trainer_repo.get_by_id(conversation.trainer_id, conversation.organization_id)
        if not trainer:
            return None
        employee = await self.employee_repo.get_by_id(trainer.employee_id, conversation.organization_id)
        return employee.user_id if employee else None

    async def list_messages(self, conversation: MessagingConversation, viewer_user_id: uuid.UUID) -> list[MessagingMessage]:
        await self.message_repo.mark_read(conversation.id, viewer_user_id)
        return await self.message_repo.list_for_conversation(conversation.id)

    # ---- attachments ----

    async def request_attachment_upload(
        self,
        organization_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        entity_id: uuid.UUID,
        filename: str,
        content_type: str,
    ) -> tuple[uuid.UUID, str]:
        if not (content_type.startswith("image/") or content_type.startswith("video/")):
            raise ValidationError("Only photo or video attachments are allowed in chat.")
        document, upload_url = await self.document_service.request_upload(
            organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            entity_type="message_attachment",
            entity_id=entity_id,
            filename=filename,
            content_type=content_type,
        )
        return document.id, upload_url

    async def confirm_attachment_upload(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> uuid.UUID:
        document = await self.document_service.confirm_upload(
            document_id, organization_id, max_size_bytes=MESSAGE_ATTACHMENT_MAX_SIZE_BYTES
        )
        return document.id

    # ---- admin oversight (read-only) ----

    async def list_conversations_for_admin(
        self,
        organization_id: uuid.UUID,
        student_id: uuid.UUID | None = None,
        trainer_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        conversations, total = await self.conversation_repo.list_for_organization(
            organization_id, student_id=student_id, trainer_id=trainer_id, skip=skip, limit=limit
        )
        students = await self.student_repo.list_for_ids([c.student_id for c in conversations], organization_id)
        trainer_rows = await self.trainer_repo.list_with_employee_for_ids(
            [c.trainer_id for c in conversations], organization_id
        )
        student_name_by_id = {s.id: s.full_name for s in students}
        trainer_name_by_id = {t.id: e.full_name for t, e in trainer_rows}
        enriched = []
        for c in conversations:
            last_message = await self.message_repo.get_last_message(c.id)
            enriched.append(
                {
                    "conversation": c,
                    "student_name": student_name_by_id.get(c.student_id, "Unknown"),
                    "trainer_name": trainer_name_by_id.get(c.trainer_id, "Unknown"),
                    "last_message": last_message,
                }
            )
        return enriched, total

    async def get_conversation_for_admin(self, conversation_id: uuid.UUID, organization_id: uuid.UUID) -> MessagingConversation:
        conversation = await self.conversation_repo.get_by_id(conversation_id, organization_id)
        if not conversation:
            raise NotFoundError("MessagingConversation", conversation_id)
        return conversation

    async def list_messages_for_admin(self, conversation_id: uuid.UUID, organization_id: uuid.UUID) -> list[MessagingMessage]:
        conversation = await self.get_conversation_for_admin(conversation_id, organization_id)
        return await self.message_repo.list_for_conversation(conversation.id)
