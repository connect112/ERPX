import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.ai.models import (
    AIEvaluationResult,
    AIInsightReport,
    Conversation,
    ConversationType,
    CourseRecommendationLog,
    GeneratedQuestionBatch,
    GeneratedQuestionItem,
    GeneratedResume,
    InsightReportType,
    InterviewExchange,
    InterviewSession,
    InterviewSessionStatus,
    Message,
    MessageRole,
)


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Conversation:
        conversation = Conversation(**fields)
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID, organization_id: uuid.UUID) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.organization_id == organization_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        organization_id: uuid.UUID,
        initiated_by_user_id: uuid.UUID,
        conversation_type: ConversationType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Conversation], int]:
        conditions = [
            Conversation.organization_id == organization_id,
            Conversation.initiated_by_user_id == initiated_by_user_id,
        ]
        if conversation_type is not None:
            conditions.append(Conversation.conversation_type == conversation_type)

        count_result = await self.db.execute(select(func.count()).select_from(Conversation).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Conversation).where(*conditions).order_by(Conversation.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, conversation: Conversation, **fields) -> Conversation:
        for key, value in fields.items():
            if value is not None:
                setattr(conversation, key, value)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Message:
        message = Message(**fields)
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self.db.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())


class GeneratedQuestionBatchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, items: list[dict], **fields) -> GeneratedQuestionBatch:
        batch = GeneratedQuestionBatch(**fields)
        self.db.add(batch)
        await self.db.flush()
        for item in items:
            self.db.add(GeneratedQuestionItem(batch_id=batch.id, **item))
        await self.db.flush()
        return await self.get_by_id(batch.id, batch.organization_id)

    async def get_by_id(self, batch_id: uuid.UUID, organization_id: uuid.UUID) -> GeneratedQuestionBatch | None:
        result = await self.db.execute(
            select(GeneratedQuestionBatch)
            .where(GeneratedQuestionBatch.id == batch_id, GeneratedQuestionBatch.organization_id == organization_id)
            .options(selectinload(GeneratedQuestionBatch.items))
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[GeneratedQuestionBatch], int]:
        conditions = [GeneratedQuestionBatch.organization_id == organization_id]
        count_result = await self.db.execute(
            select(func.count()).select_from(GeneratedQuestionBatch).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(GeneratedQuestionBatch)
            .where(*conditions)
            .options(selectinload(GeneratedQuestionBatch.items))
            .order_by(GeneratedQuestionBatch.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), total


class GeneratedQuestionItemRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, item_id: uuid.UUID) -> GeneratedQuestionItem | None:
        result = await self.db.execute(select(GeneratedQuestionItem).where(GeneratedQuestionItem.id == item_id))
        return result.scalar_one_or_none()

    async def update(self, item: GeneratedQuestionItem, **fields) -> GeneratedQuestionItem:
        for key, value in fields.items():
            if value is not None:
                setattr(item, key, value)
        await self.db.flush()
        await self.db.refresh(item)
        return item


class GeneratedResumeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> GeneratedResume:
        resume = GeneratedResume(**fields)
        self.db.add(resume)
        await self.db.flush()
        await self.db.refresh(resume)
        return resume

    async def get_by_id(self, resume_id: uuid.UUID, organization_id: uuid.UUID) -> GeneratedResume | None:
        result = await self.db.execute(
            select(GeneratedResume).where(
                GeneratedResume.id == resume_id, GeneratedResume.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(self, student_id: uuid.UUID) -> list[GeneratedResume]:
        result = await self.db.execute(
            select(GeneratedResume)
            .where(GeneratedResume.student_id == student_id)
            .order_by(GeneratedResume.version.desc())
        )
        return list(result.scalars().all())

    async def latest_version_for_student(self, student_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(GeneratedResume.version), 0)).where(
                GeneratedResume.student_id == student_id
            )
        )
        return result.scalar_one()


class InterviewSessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> InterviewSession:
        session = InterviewSession(**fields)
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID, organization_id: uuid.UUID) -> InterviewSession | None:
        result = await self.db.execute(
            select(InterviewSession)
            .where(InterviewSession.id == session_id, InterviewSession.organization_id == organization_id)
            .options(selectinload(InterviewSession.exchanges))
        )
        return result.scalar_one_or_none()

    async def list_for_student(
        self, student_id: uuid.UUID, status: InterviewSessionStatus | None = None
    ) -> list[InterviewSession]:
        conditions = [InterviewSession.student_id == student_id]
        if status is not None:
            conditions.append(InterviewSession.status == status)
        result = await self.db.execute(
            select(InterviewSession).where(*conditions).order_by(InterviewSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, session: InterviewSession, **fields) -> InterviewSession:
        for key, value in fields.items():
            if value is not None:
                setattr(session, key, value)
        await self.db.flush()
        await self.db.refresh(session)
        return session


class InterviewExchangeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> InterviewExchange:
        exchange = InterviewExchange(**fields)
        self.db.add(exchange)
        await self.db.flush()
        await self.db.refresh(exchange)
        return exchange

    async def get_by_id(self, exchange_id: uuid.UUID) -> InterviewExchange | None:
        result = await self.db.execute(select(InterviewExchange).where(InterviewExchange.id == exchange_id))
        return result.scalar_one_or_none()

    async def count_for_session(self, session_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(InterviewExchange).where(InterviewExchange.session_id == session_id)
        )
        return result.scalar_one()

    async def update(self, exchange: InterviewExchange, **fields) -> InterviewExchange:
        for key, value in fields.items():
            if value is not None:
                setattr(exchange, key, value)
        await self.db.flush()
        await self.db.refresh(exchange)
        return exchange


class AIEvaluationResultRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AIEvaluationResult:
        evaluation = AIEvaluationResult(**fields)
        self.db.add(evaluation)
        await self.db.flush()
        await self.db.refresh(evaluation)
        return evaluation

    async def get_by_id(self, evaluation_id: uuid.UUID, organization_id: uuid.UUID) -> AIEvaluationResult | None:
        result = await self.db.execute(
            select(AIEvaluationResult).where(
                AIEvaluationResult.id == evaluation_id, AIEvaluationResult.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_reference(self, reference_type: str, reference_id: uuid.UUID) -> list[AIEvaluationResult]:
        result = await self.db.execute(
            select(AIEvaluationResult)
            .where(
                AIEvaluationResult.reference_type == reference_type,
                AIEvaluationResult.reference_id == reference_id,
            )
            .order_by(AIEvaluationResult.created_at.desc())
        )
        return list(result.scalars().all())


class CourseRecommendationLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> CourseRecommendationLog:
        log = CourseRecommendationLog(**fields)
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def list_for_student(self, student_id: uuid.UUID) -> list[CourseRecommendationLog]:
        result = await self.db.execute(
            select(CourseRecommendationLog)
            .where(CourseRecommendationLog.student_id == student_id)
            .order_by(CourseRecommendationLog.created_at.desc())
        )
        return list(result.scalars().all())


class AIInsightReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AIInsightReport:
        report = AIInsightReport(**fields)
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def get_by_id(self, report_id: uuid.UUID, organization_id: uuid.UUID) -> AIInsightReport | None:
        result = await self.db.execute(
            select(AIInsightReport).where(
                AIInsightReport.id == report_id, AIInsightReport.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        report_type: InsightReportType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AIInsightReport], int]:
        conditions = [AIInsightReport.organization_id == organization_id]
        if report_type is not None:
            conditions.append(AIInsightReport.report_type == report_type)

        count_result = await self.db.execute(select(func.count()).select_from(AIInsightReport).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(AIInsightReport)
            .where(*conditions)
            .order_by(AIInsightReport.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total
