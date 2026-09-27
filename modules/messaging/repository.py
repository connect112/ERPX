import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.messaging.models import MessagingConversation, MessagingMessage


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_pair(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, trainer_id: uuid.UUID
    ) -> MessagingConversation | None:
        result = await self.db.execute(
            select(MessagingConversation).where(
                MessagingConversation.organization_id == organization_id,
                MessagingConversation.student_id == student_id,
                MessagingConversation.trainer_id == trainer_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, trainer_id: uuid.UUID
    ) -> MessagingConversation:
        existing = await self.get_by_pair(organization_id, student_id, trainer_id)
        if existing:
            return existing
        conversation = MessagingConversation(
            organization_id=organization_id, student_id=student_id, trainer_id=trainer_id
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def get_by_id(
        self, conversation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> MessagingConversation | None:
        result = await self.db.execute(
            select(MessagingConversation).where(
                MessagingConversation.id == conversation_id, MessagingConversation.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(
        self, student_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[MessagingConversation]:
        result = await self.db.execute(
            select(MessagingConversation)
            .where(MessagingConversation.student_id == student_id, MessagingConversation.organization_id == organization_id)
            .order_by(MessagingConversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_trainer(
        self, trainer_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[MessagingConversation]:
        result = await self.db.execute(
            select(MessagingConversation)
            .where(MessagingConversation.trainer_id == trainer_id, MessagingConversation.organization_id == organization_id)
            .order_by(MessagingConversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        student_id: uuid.UUID | None = None,
        trainer_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[MessagingConversation], int]:
        conditions = [MessagingConversation.organization_id == organization_id]
        if student_id is not None:
            conditions.append(MessagingConversation.student_id == student_id)
        if trainer_id is not None:
            conditions.append(MessagingConversation.trainer_id == trainer_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(MessagingConversation).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(MessagingConversation)
            .where(*conditions)
            .order_by(MessagingConversation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> MessagingMessage:
        message = MessagingMessage(**fields)
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def list_for_conversation(
        self, conversation_id: uuid.UUID, skip: int = 0, limit: int = 200
    ) -> list[MessagingMessage]:
        result = await self.db.execute(
            select(MessagingMessage)
            .where(MessagingMessage.conversation_id == conversation_id)
            .order_by(MessagingMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_last_message(self, conversation_id: uuid.UUID) -> MessagingMessage | None:
        result = await self.db.execute(
            select(MessagingMessage)
            .where(MessagingMessage.conversation_id == conversation_id)
            .order_by(MessagingMessage.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_read(self, conversation_id: uuid.UUID, reader_user_id: uuid.UUID) -> None:
        """Marks every message in this conversation not sent by the reader
        as read -- called whenever the reader opens/lists the thread."""
        await self.db.execute(
            update(MessagingMessage)
            .where(
                MessagingMessage.conversation_id == conversation_id,
                MessagingMessage.sender_user_id != reader_user_id,
                MessagingMessage.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.db.flush()

    async def unread_count_for_conversations(
        self, conversation_ids: list[uuid.UUID], reader_user_id: uuid.UUID
    ) -> int:
        if not conversation_ids:
            return 0
        result = await self.db.execute(
            select(func.count())
            .select_from(MessagingMessage)
            .where(
                MessagingMessage.conversation_id.in_(conversation_ids),
                MessagingMessage.sender_user_id != reader_user_id,
                MessagingMessage.read_at.is_(None),
            )
        )
        return result.scalar_one()

    async def get_attachment_usage(self, document_id: uuid.UUID) -> MessagingMessage | None:
        """Whether this document is already attached to some message --
        guards against replaying a confirmed upload into a second,
        unrelated message (possibly in a different conversation)."""
        result = await self.db.execute(
            select(MessagingMessage).where(MessagingMessage.attachment_document_id == document_id)
        )
        return result.scalar_one_or_none()
