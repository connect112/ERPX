import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.accounting.reports.service import ReportService
from modules.ai.models import (
    AIEvaluationResult,
    Conversation,
    ConversationType,
    CourseRecommendationLog,
    GeneratedQuestionBatch,
    GeneratedResume,
    InsightReportType,
    InterviewExchange,
    InterviewSession,
    InterviewSessionStatus,
    Message,
    MessageRole,
)
from modules.ai.repository import (
    AIEvaluationResultRepository,
    AIInsightReportRepository,
    ConversationRepository,
    CourseRecommendationLogRepository,
    GeneratedQuestionBatchRepository,
    GeneratedQuestionItemRepository,
    GeneratedResumeRepository,
    InterviewExchangeRepository,
    InterviewSessionRepository,
    MessageRepository,
)
from modules.attendance.repository import AttendanceRepository
from modules.courses.repository import CourseRepository
from modules.crm.leads.repository import LeadRepository
from modules.examinations.question_bank.repository import QuestionRepository
from modules.examinations.results.service import ResultsService
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.repository import StudentRepository
from packages.ai.client import AIMessage, get_ai_client
from packages.ai.prompts import (
    assignment_evaluation_system_prompt,
    chat_assistant_system_prompt,
    course_recommendation_system_prompt,
    insight_report_system_prompt,
    interview_feedback_system_prompt,
    interview_question_system_prompt,
    interview_summary_system_prompt,
    question_generator_system_prompt,
    resume_builder_system_prompt,
    tutor_system_prompt,
)

logger = get_logger(__name__)


def _parse_json_response(text: str) -> dict | list:
    """AI responses are instructed to return raw JSON, but models sometimes
    still wrap it in ```json fences despite instructions — strip those before parsing."""
    cleaned = text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("ai_response_not_json", text=text[:500])
        raise ValidationError("The AI returned a response that could not be parsed. Please try again.") from exc


class ConversationService:
    """Backs both AI Tutor (conversation_type=TUTOR) and AI Chat Assistant (CHAT_ASSISTANT)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ConversationRepository(db)
        self.message_repo = MessageRepository(db)
        self.student_repo = StudentRepository(db)
        self.course_repo = CourseRepository(db)
        self.ai_client = get_ai_client()

    async def start_conversation(
        self,
        organization_id: uuid.UUID,
        initiated_by_user_id: uuid.UUID,
        conversation_type: ConversationType,
        student_id: uuid.UUID | None = None,
        course_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> Conversation:
        if student_id is not None:
            student = await self.student_repo.get_by_id(student_id, organization_id)
            if not student:
                raise NotFoundError("Student", student_id)
        if course_id is not None:
            course = await self.course_repo.get_by_id(course_id, organization_id)
            if not course:
                raise NotFoundError("Course", course_id)

        conversation = await self.repo.create(
            organization_id=organization_id,
            initiated_by_user_id=initiated_by_user_id,
            conversation_type=conversation_type,
            student_id=student_id,
            course_id=course_id,
            title=title,
        )
        logger.info("ai_conversation_started", conversation_id=str(conversation.id), type=conversation_type.value)
        return conversation

    async def get_conversation(self, conversation_id: uuid.UUID, organization_id: uuid.UUID) -> Conversation:
        conversation = await self.repo.get_by_id(conversation_id, organization_id)
        if not conversation:
            raise NotFoundError("Conversation", conversation_id)
        return conversation

    async def list_conversations(self, organization_id: uuid.UUID, initiated_by_user_id: uuid.UUID, **filters):
        return await self.repo.list_for_user(organization_id, initiated_by_user_id, **filters)

    async def send_message(self, conversation_id: uuid.UUID, organization_id: uuid.UUID, content: str) -> Message:
        conversation = await self.get_conversation(conversation_id, organization_id)
        if conversation.is_archived:
            raise ValidationError("This conversation is archived and cannot receive new messages.")

        await self.message_repo.create(conversation_id=conversation_id, role=MessageRole.USER, content=content)
        history = await self.message_repo.list_for_conversation(conversation_id)

        if conversation.conversation_type == ConversationType.TUTOR:
            course_name = None
            if conversation.course_id is not None:
                course = await self.course_repo.get_by_id(conversation.course_id, organization_id)
                course_name = course.title if course else None
            system_prompt = tutor_system_prompt(course_name)
        else:
            system_prompt = chat_assistant_system_prompt()

        ai_messages = [AIMessage(role=m.role.value, content=m.content) for m in history]
        result = await self.ai_client.complete(system_prompt, ai_messages)

        assistant_message = await self.message_repo.create(
            conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=result.text
        )
        logger.info("ai_message_exchanged", conversation_id=str(conversation_id), tokens=result.output_tokens)
        return assistant_message

    async def archive_conversation(self, conversation_id: uuid.UUID, organization_id: uuid.UUID) -> Conversation:
        conversation = await self.get_conversation(conversation_id, organization_id)
        return await self.repo.update(conversation, is_archived=True)


class QuestionGeneratorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.batch_repo = GeneratedQuestionBatchRepository(db)
        self.item_repo = GeneratedQuestionItemRepository(db)
        self.course_repo = CourseRepository(db)
        self.question_repo = QuestionRepository(db)
        self.ai_client = get_ai_client()

    async def generate(
        self,
        organization_id: uuid.UUID,
        requested_by_user_id: uuid.UUID,
        topic: str,
        question_type,
        difficulty,
        count: int,
        course_id: uuid.UUID | None = None,
    ) -> GeneratedQuestionBatch:
        if course_id is not None:
            course = await self.course_repo.get_by_id(course_id, organization_id)
            if not course:
                raise NotFoundError("Course", course_id)

        system_prompt = question_generator_system_prompt(topic, question_type.value, difficulty.value, count)
        result = await self.ai_client.complete(
            system_prompt, [AIMessage(role="user", content=f"Generate the questions about: {topic}")]
        )
        parsed = _parse_json_response(result.text)
        if not isinstance(parsed, list):
            raise ValidationError("The AI did not return a list of questions. Please try again.")

        items = []
        for entry in parsed:
            items.append(
                {
                    "question_text": entry.get("question_text", "").strip(),
                    "options": entry.get("options"),
                    "correct_answer": entry.get("correct_answer"),
                    "explanation": entry.get("explanation"),
                }
            )

        batch = await self.batch_repo.create(
            items=items,
            organization_id=organization_id,
            requested_by_user_id=requested_by_user_id,
            course_id=course_id,
            topic=topic,
            question_type=question_type,
            difficulty=difficulty,
            requested_count=count,
        )
        logger.info("ai_questions_generated", batch_id=str(batch.id), count=len(items))
        return batch

    async def get_batch(self, batch_id: uuid.UUID, organization_id: uuid.UUID) -> GeneratedQuestionBatch:
        batch = await self.batch_repo.get_by_id(batch_id, organization_id)
        if not batch:
            raise NotFoundError("Generated question batch", batch_id)
        return batch

    async def list_batches(self, organization_id: uuid.UUID, **filters):
        return await self.batch_repo.list_for_organization(organization_id, **filters)

    async def review_item(self, item_id: uuid.UUID, **fields):
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            raise NotFoundError("Generated question item", item_id)
        return await self.item_repo.update(item, **fields)

    async def approve_item(
        self, item_id: uuid.UUID, organization_id: uuid.UUID, default_marks: int
    ):
        item = await self.item_repo.get_by_id(item_id)
        if not item:
            raise NotFoundError("Generated question item", item_id)
        if item.is_approved:
            raise ValidationError("This question has already been approved and imported.")

        batch = await self.batch_repo.get_by_id(item.batch_id, organization_id)
        if not batch:
            raise NotFoundError("Generated question batch", item.batch_id)

        question = await self.question_repo.create(
            organization_id=organization_id,
            course_id=batch.course_id,
            question_text=item.question_text,
            question_type=batch.question_type,
            options=item.options,
            correct_answer=item.correct_answer,
            default_marks=default_marks,
            difficulty=batch.difficulty,
        )
        updated_item = await self.item_repo.update(item, is_approved=True, imported_question_id=question.id)
        logger.info("ai_question_approved", item_id=str(item_id), question_id=str(question.id))
        return updated_item


class ResumeBuilderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = GeneratedResumeRepository(db)
        self.student_repo = StudentRepository(db)
        self.ai_client = get_ai_client()

    async def generate_resume(
        self,
        organization_id: uuid.UUID,
        student_id: uuid.UUID,
        target_role: str | None,
        education_summary: str,
        skills_summary: str,
        experience_summary: str | None,
        projects_summary: str | None,
    ) -> GeneratedResume:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        input_summary = (
            f"Name: {student.full_name}\n"
            f"Education: {education_summary}\n"
            f"Skills: {skills_summary}\n"
            f"Experience: {experience_summary or 'N/A'}\n"
            f"Projects: {projects_summary or 'N/A'}"
        )
        system_prompt = resume_builder_system_prompt(target_role)
        result = await self.ai_client.complete(
            system_prompt, [AIMessage(role="user", content=f"Candidate details:\n\n{input_summary}")]
        )

        next_version = await self.repo.latest_version_for_student(student_id) + 1
        resume = await self.repo.create(
            organization_id=organization_id,
            student_id=student_id,
            target_role=target_role,
            input_summary=input_summary,
            content=result.text,
            version=next_version,
        )
        logger.info("ai_resume_generated", resume_id=str(resume.id), student_id=str(student_id))
        return resume

    async def get_resume(self, resume_id: uuid.UUID, organization_id: uuid.UUID) -> GeneratedResume:
        resume = await self.repo.get_by_id(resume_id, organization_id)
        if not resume:
            raise NotFoundError("Generated resume", resume_id)
        return resume

    async def list_for_student(self, student_id: uuid.UUID, organization_id: uuid.UUID) -> list[GeneratedResume]:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return await self.repo.list_for_student(student_id)


class InterviewSimulatorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = InterviewSessionRepository(db)
        self.exchange_repo = InterviewExchangeRepository(db)
        self.student_repo = StudentRepository(db)
        self.ai_client = get_ai_client()

    async def start_session(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, role_or_topic: str
    ) -> InterviewSession:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        session = await self.session_repo.create(
            organization_id=organization_id, student_id=student_id, role_or_topic=role_or_topic
        )

        system_prompt = interview_question_system_prompt(role_or_topic, previous_qa="")
        result = await self.ai_client.complete(system_prompt, [AIMessage(role="user", content="Begin the interview.")])
        await self.exchange_repo.create(session_id=session.id, order_index=0, question_text=result.text.strip())

        logger.info("ai_interview_started", session_id=str(session.id), student_id=str(student_id))
        return await self.get_session(session.id, organization_id)

    async def get_session(self, session_id: uuid.UUID, organization_id: uuid.UUID) -> InterviewSession:
        session = await self.session_repo.get_by_id(session_id, organization_id)
        if not session:
            raise NotFoundError("Interview session", session_id)
        return session

    async def list_for_student(self, student_id: uuid.UUID, organization_id: uuid.UUID, **filters):
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)
        return await self.session_repo.list_for_student(student_id, **filters)

    async def submit_answer(
        self, session_id: uuid.UUID, organization_id: uuid.UUID, answer: str
    ) -> InterviewSession:
        session = await self.get_session(session_id, organization_id)
        if session.status != InterviewSessionStatus.IN_PROGRESS:
            raise ValidationError("This interview session has already been completed.")

        current_exchange = session.exchanges[-1] if session.exchanges else None
        if current_exchange is None or current_exchange.student_answer is not None:
            raise ValidationError("There is no pending question to answer in this session.")

        feedback_result = await self.ai_client.complete(
            interview_feedback_system_prompt(),
            [AIMessage(role="user", content=f"Question: {current_exchange.question_text}\n\nCandidate answer: {answer}")],
        )
        parsed = _parse_json_response(feedback_result.text)
        await self.exchange_repo.update(
            current_exchange,
            student_answer=answer,
            ai_feedback=parsed.get("feedback"),
            score_out_of_10=parsed.get("score_out_of_10"),
        )

        transcript = "\n".join(
            f"Q{i + 1}: {e.question_text}\nA{i + 1}: {e.student_answer or ''}"
            for i, e in enumerate(session.exchanges)
        )
        next_question_result = await self.ai_client.complete(
            interview_question_system_prompt(session.role_or_topic, transcript),
            [AIMessage(role="user", content="Ask the next question, or if the interview feels complete, ask a wrap-up question.")],
        )
        next_index = await self.exchange_repo.count_for_session(session_id)
        await self.exchange_repo.create(
            session_id=session_id, order_index=next_index, question_text=next_question_result.text.strip()
        )

        logger.info("ai_interview_answer_submitted", session_id=str(session_id))
        return await self.get_session(session_id, organization_id)

    async def complete_session(self, session_id: uuid.UUID, organization_id: uuid.UUID) -> InterviewSession:
        session = await self.get_session(session_id, organization_id)
        if session.status != InterviewSessionStatus.IN_PROGRESS:
            raise ValidationError("This interview session has already been completed.")

        transcript = "\n".join(
            f"Q{i + 1}: {e.question_text}\nA{i + 1}: {e.student_answer or '(not answered)'}\n"
            f"Feedback: {e.ai_feedback or 'N/A'}"
            for i, e in enumerate(session.exchanges)
        )
        summary_result = await self.ai_client.complete(
            interview_summary_system_prompt(), [AIMessage(role="user", content=f"Transcript:\n\n{transcript}")]
        )

        scored_exchanges = [e for e in session.exchanges if e.score_out_of_10 is not None]
        overall_score = (
            round(sum(float(e.score_out_of_10) for e in scored_exchanges) / len(scored_exchanges), 1)
            if scored_exchanges
            else None
        )

        updated = await self.session_repo.update(
            session,
            status=InterviewSessionStatus.COMPLETED,
            overall_feedback=summary_result.text,
            overall_score=overall_score,
        )
        logger.info("ai_interview_completed", session_id=str(session_id), overall_score=overall_score)
        return updated


class AssignmentEvaluationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AIEvaluationResultRepository(db)
        self.ai_client = get_ai_client()

    async def evaluate(
        self,
        organization_id: uuid.UUID,
        evaluated_by_user_id: uuid.UUID | None,
        reference_type: str,
        reference_id: uuid.UUID,
        submission_text: str,
        rubric_text: str | None,
    ) -> AIEvaluationResult:
        system_prompt = assignment_evaluation_system_prompt(rubric_text)
        result = await self.ai_client.complete(
            system_prompt, [AIMessage(role="user", content=f"Submission:\n\n{submission_text}")]
        )
        parsed = _parse_json_response(result.text)

        evaluation = await self.repo.create(
            organization_id=organization_id,
            evaluated_by_user_id=evaluated_by_user_id,
            reference_type=reference_type,
            reference_id=reference_id,
            score_out_of_100=parsed.get("score_out_of_100"),
            feedback=parsed.get("feedback", ""),
            strengths=parsed.get("strengths"),
            improvement_areas=parsed.get("improvement_areas"),
        )
        logger.info("ai_evaluation_created", evaluation_id=str(evaluation.id), reference_type=reference_type)
        return evaluation

    async def get_evaluation(self, evaluation_id: uuid.UUID, organization_id: uuid.UUID) -> AIEvaluationResult:
        evaluation = await self.repo.get_by_id(evaluation_id, organization_id)
        if not evaluation:
            raise NotFoundError("AI evaluation result", evaluation_id)
        return evaluation

    async def list_for_reference(self, reference_type: str, reference_id: uuid.UUID) -> list[AIEvaluationResult]:
        return await self.repo.list_for_reference(reference_type, reference_id)


class CourseRecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.log_repo = CourseRecommendationLogRepository(db)
        self.student_repo = StudentRepository(db)
        self.course_repo = CourseRepository(db)
        self.enrollment_repo = EnrollmentRepository(db)
        self.ai_client = get_ai_client()

    async def recommend(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, stated_interests: str | None
    ) -> dict:
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        enrollments = await self.enrollment_repo.list_for_student(student_id)
        enrolled_course_ids = {e.course_id for e in enrollments}

        catalog, _ = await self.course_repo.list_for_organization(
            organization_id, is_published=True, skip=0, limit=200
        )
        available_catalog = [c for c in catalog if c.id not in enrolled_course_ids]
        if not available_catalog:
            return {"student_id": student_id, "recommendations": []}

        catalog_text = "\n".join(
            f"- course_id: {c.id} | title: {c.title} | level: {c.level.value} | "
            f"description: {c.short_description or c.description or ''}"
            for c in available_catalog
        )
        completed_text = ", ".join(str(cid) for cid in enrolled_course_ids) or "None yet"
        user_prompt = (
            f"Student's currently enrolled/completed course IDs: {completed_text}\n"
            f"Stated interests: {stated_interests or 'Not specified'}\n\n"
            f"Available course catalog:\n{catalog_text}"
        )

        result = await self.ai_client.complete(course_recommendation_system_prompt(), [AIMessage(role="user", content=user_prompt)])
        parsed = _parse_json_response(result.text)
        if not isinstance(parsed, list):
            raise ValidationError("The AI did not return a list of recommendations. Please try again.")

        courses_by_id = {str(c.id): c for c in available_catalog}
        recommendations = []
        recommended_ids = []
        for entry in parsed:
            course_id_str = str(entry.get("course_id", ""))
            course = courses_by_id.get(course_id_str)
            if course is None:
                continue
            recommendations.append({"course_id": course.id, "course_name": course.title, "reason": entry.get("reason", "")})
            recommended_ids.append(course_id_str)

        await self.log_repo.create(
            organization_id=organization_id,
            student_id=student_id,
            recommended_course_ids=recommended_ids,
            rationale=stated_interests,
        )
        logger.info("ai_course_recommendation_generated", student_id=str(student_id), count=len(recommendations))
        return {"student_id": student_id, "recommendations": recommendations}


class AIAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AIInsightReportRepository(db)
        self.lead_repo = LeadRepository(db)
        self.attendance_repo = AttendanceRepository(db)
        self.student_repo = StudentRepository(db)
        self.enrollment_repo = EnrollmentRepository(db)
        self.report_service = ReportService(db)
        self.ai_client = get_ai_client()

    async def _build_snapshot(
        self, organization_id: uuid.UUID, report_type: InsightReportType, reference_id: uuid.UUID | None
    ) -> str:
        if report_type == InsightReportType.SALES_PIPELINE:
            leads, total = await self.lead_repo.list_for_organization(organization_id, skip=0, limit=10_000)
            by_status: dict[str, int] = {}
            for lead in leads:
                by_status[lead.status.value] = by_status.get(lead.status.value, 0) + 1
            return f"Total leads: {total}\nBreakdown by status: {by_status}"

        if report_type == InsightReportType.ATTENDANCE_TRENDS:
            today = date.today()
            records, total = await self.attendance_repo.list_for_organization(
                organization_id, attendance_date=None, skip=0, limit=10_000
            )
            recent = [r for r in records if r.attendance_date >= today - timedelta(days=30)]
            by_status: dict[str, int] = {}
            for record in recent:
                by_status[record.status.value] = by_status.get(record.status.value, 0) + 1
            return f"Attendance records in the last 30 days: {len(recent)}\nBreakdown by status: {by_status}"

        if report_type == InsightReportType.FINANCIAL_HEALTH:
            today = date.today()
            month_start = today.replace(day=1)
            pnl = await self.report_service.profit_and_loss(organization_id, month_start, today)
            return (
                f"Period: {month_start} to {today}\n"
                f"Total income: {pnl['total_income']}\n"
                f"Total expense: {pnl['total_expense']}\n"
                f"Net profit: {pnl['net_profit']}"
            )

        if report_type == InsightReportType.STUDENT_PERFORMANCE:
            if reference_id is None:
                raise ValidationError("reference_id (student_id) is required for a student_performance report.")
            student = await self.student_repo.get_by_id(reference_id, organization_id)
            if not student:
                raise NotFoundError("Student", reference_id)
            enrollments = await self.enrollment_repo.list_for_student(reference_id)
            results_service = ResultsService(self.db)
            lines = [f"Student: {student.full_name}"]
            for enrollment in enrollments:
                try:
                    result = await results_service.get_student_course_result(
                        reference_id, enrollment.course_id, organization_id
                    )
                    lines.append(
                        f"- Course {enrollment.course_id}: {result.overall_percentage}% ({result.overall_status})"
                    )
                except NotFoundError:
                    continue
            return "\n".join(lines)

        raise ValidationError(f"Unsupported report type: {report_type.value}")

    async def generate_report(
        self,
        organization_id: uuid.UUID,
        generated_by_user_id: uuid.UUID | None,
        report_type: InsightReportType,
        reference_id: uuid.UUID | None,
    ):
        snapshot = await self._build_snapshot(organization_id, report_type, reference_id)
        system_prompt = insight_report_system_prompt(report_type.value)
        result = await self.ai_client.complete(system_prompt, [AIMessage(role="user", content=snapshot)])

        report = await self.repo.create(
            organization_id=organization_id,
            generated_by_user_id=generated_by_user_id,
            report_type=report_type,
            reference_id=reference_id,
            content=result.text,
        )
        logger.info("ai_insight_report_generated", report_id=str(report.id), report_type=report_type.value)
        return report

    async def get_report(self, report_id: uuid.UUID, organization_id: uuid.UUID):
        report = await self.repo.get_by_id(report_id, organization_id)
        if not report:
            raise NotFoundError("AI insight report", report_id)
        return report

    async def list_reports(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)
