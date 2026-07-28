import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.ai.models import ConversationType, InsightReportType, InterviewSessionStatus
from modules.ai.schemas import (
    AIEvaluationResultPublic,
    AIInsightReportPublic,
    ApproveQuestionItemRequest,
    ConversationPublic,
    CourseRecommendationResponse,
    EvaluateSubmissionRequest,
    GenerateInsightReportRequest,
    GenerateQuestionsRequest,
    GenerateResumeRequest,
    GeneratedQuestionBatchPublic,
    GeneratedQuestionItemPublic,
    GeneratedResumePublic,
    InterviewSessionPublic,
    MessagePublic,
    MessageResponse,
    RecommendCoursesRequest,
    ReviewQuestionItemRequest,
    SendMessageRequest,
    StartConversationRequest,
    StartInterviewRequest,
    SubmitInterviewAnswerRequest,
)
from modules.ai.service import (
    AIAnalyticsService,
    AssignmentEvaluationService,
    ConversationService,
    CourseRecommendationService,
    InterviewSimulatorService,
    QuestionGeneratorService,
    ResumeBuilderService,
)
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- AI Tutor / AI Chat Assistant ----


@router.post("/conversations", response_model=ConversationPublic, status_code=status.HTTP_201_CREATED)
async def start_conversation(
    payload: StartConversationRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.conversations.use")),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conversation = await service.start_conversation(organization_id, initiated_by_user_id=user.id, **payload.model_dump())
    return ConversationPublic.model_validate(conversation)


@router.get("/conversations", response_model=dict)
async def list_conversations(
    conversation_type: ConversationType | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.conversations.use")),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conversations, total = await service.list_conversations(
        organization_id, user.id, conversation_type=conversation_type, skip=skip, limit=limit
    )
    return {
        "items": [ConversationPublic.model_validate(c) for c in conversations],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/conversations/{conversation_id}", response_model=ConversationPublic)
async def get_conversation(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.conversations.use")),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conversation = await service.get_conversation(conversation_id, organization_id)
    return ConversationPublic.model_validate(conversation)


@router.post("/conversations/{conversation_id}/messages", response_model=MessagePublic, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.conversations.use")),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    message = await service.send_message(conversation_id, organization_id, payload.content)
    return MessagePublic.model_validate(message)


@router.post("/conversations/{conversation_id}/archive", response_model=ConversationPublic)
async def archive_conversation(
    conversation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.conversations.use")),
    db: AsyncSession = Depends(get_db),
):
    service = ConversationService(db)
    conversation = await service.archive_conversation(conversation_id, organization_id)
    return ConversationPublic.model_validate(conversation)


# ---- AI Question Generator ----


@router.post("/question-batches", response_model=GeneratedQuestionBatchPublic, status_code=status.HTTP_201_CREATED)
async def generate_questions(
    payload: GenerateQuestionsRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.questions.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionGeneratorService(db)
    batch = await service.generate(organization_id, requested_by_user_id=user.id, **payload.model_dump())
    return GeneratedQuestionBatchPublic.model_validate(batch)


@router.get("/question-batches", response_model=dict)
async def list_question_batches(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.questions.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionGeneratorService(db)
    batches, total = await service.list_batches(organization_id, skip=skip, limit=limit)
    return {
        "items": [GeneratedQuestionBatchPublic.model_validate(b) for b in batches],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/question-batches/{batch_id}", response_model=GeneratedQuestionBatchPublic)
async def get_question_batch(
    batch_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.questions.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionGeneratorService(db)
    batch = await service.get_batch(batch_id, organization_id)
    return GeneratedQuestionBatchPublic.model_validate(batch)


@router.patch("/question-items/{item_id}", response_model=GeneratedQuestionItemPublic)
async def review_question_item(
    item_id: uuid.UUID,
    payload: ReviewQuestionItemRequest,
    user: User = Depends(require_permissions("ai.questions.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionGeneratorService(db)
    item = await service.review_item(item_id, **payload.model_dump(exclude_unset=True))
    return GeneratedQuestionItemPublic.model_validate(item)


@router.post("/question-items/{item_id}/approve", response_model=GeneratedQuestionItemPublic)
async def approve_question_item(
    item_id: uuid.UUID,
    payload: ApproveQuestionItemRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.questions.approve")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionGeneratorService(db)
    item = await service.approve_item(item_id, organization_id, payload.default_marks)
    return GeneratedQuestionItemPublic.model_validate(item)


# ---- AI Resume Builder ----


@router.post("/resumes", response_model=GeneratedResumePublic, status_code=status.HTTP_201_CREATED)
async def generate_resume(
    payload: GenerateResumeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.resumes.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = ResumeBuilderService(db)
    resume = await service.generate_resume(organization_id, **payload.model_dump())
    return GeneratedResumePublic.model_validate(resume)


@router.get("/resumes/{resume_id}", response_model=GeneratedResumePublic)
async def get_resume(
    resume_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.resumes.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = ResumeBuilderService(db)
    resume = await service.get_resume(resume_id, organization_id)
    return GeneratedResumePublic.model_validate(resume)


@router.get("/resumes/students/{student_id}", response_model=list[GeneratedResumePublic])
async def list_resumes_for_student(
    student_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.resumes.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = ResumeBuilderService(db)
    resumes = await service.list_for_student(student_id, organization_id)
    return [GeneratedResumePublic.model_validate(r) for r in resumes]


# ---- AI Interview Simulator ----


@router.post("/interviews", response_model=InterviewSessionPublic, status_code=status.HTTP_201_CREATED)
async def start_interview(
    payload: StartInterviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.interviews.use")),
    db: AsyncSession = Depends(get_db),
):
    service = InterviewSimulatorService(db)
    session = await service.start_session(organization_id, **payload.model_dump())
    return InterviewSessionPublic.model_validate(session)


@router.get("/interviews/{session_id}", response_model=InterviewSessionPublic)
async def get_interview(
    session_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.interviews.use")),
    db: AsyncSession = Depends(get_db),
):
    service = InterviewSimulatorService(db)
    session = await service.get_session(session_id, organization_id)
    return InterviewSessionPublic.model_validate(session)


@router.get("/interviews/students/{student_id}", response_model=list[InterviewSessionPublic])
async def list_interviews_for_student(
    student_id: uuid.UUID,
    status_filter: InterviewSessionStatus | None = Query(default=None, alias="status"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.interviews.use")),
    db: AsyncSession = Depends(get_db),
):
    service = InterviewSimulatorService(db)
    sessions = await service.list_for_student(student_id, organization_id, status=status_filter)
    return [InterviewSessionPublic.model_validate(s) for s in sessions]


@router.post("/interviews/{session_id}/answer", response_model=InterviewSessionPublic)
async def submit_interview_answer(
    session_id: uuid.UUID,
    payload: SubmitInterviewAnswerRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.interviews.use")),
    db: AsyncSession = Depends(get_db),
):
    service = InterviewSimulatorService(db)
    session = await service.submit_answer(session_id, organization_id, payload.answer)
    return InterviewSessionPublic.model_validate(session)


@router.post("/interviews/{session_id}/complete", response_model=InterviewSessionPublic)
async def complete_interview(
    session_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.interviews.use")),
    db: AsyncSession = Depends(get_db),
):
    service = InterviewSimulatorService(db)
    session = await service.complete_session(session_id, organization_id)
    return InterviewSessionPublic.model_validate(session)


# ---- AI Assignment Evaluation ----


@router.post("/evaluations", response_model=AIEvaluationResultPublic, status_code=status.HTTP_201_CREATED)
async def evaluate_submission(
    payload: EvaluateSubmissionRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.evaluations.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentEvaluationService(db)
    evaluation = await service.evaluate(organization_id, evaluated_by_user_id=user.id, **payload.model_dump())
    return AIEvaluationResultPublic.model_validate(evaluation)


@router.get("/evaluations/{evaluation_id}", response_model=AIEvaluationResultPublic)
async def get_evaluation(
    evaluation_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.evaluations.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentEvaluationService(db)
    evaluation = await service.get_evaluation(evaluation_id, organization_id)
    return AIEvaluationResultPublic.model_validate(evaluation)


@router.get("/evaluations/by-reference/{reference_type}/{reference_id}", response_model=list[AIEvaluationResultPublic])
async def list_evaluations_for_reference(
    reference_type: str,
    reference_id: uuid.UUID,
    user: User = Depends(require_permissions("ai.evaluations.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentEvaluationService(db)
    evaluations = await service.list_for_reference(reference_type, reference_id)
    return [AIEvaluationResultPublic.model_validate(e) for e in evaluations]


# ---- AI Course Recommendation ----


@router.post("/course-recommendations", response_model=CourseRecommendationResponse)
async def recommend_courses(
    payload: RecommendCoursesRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.recommendations.use")),
    db: AsyncSession = Depends(get_db),
):
    service = CourseRecommendationService(db)
    result = await service.recommend(organization_id, **payload.model_dump())
    return CourseRecommendationResponse(**result)


# ---- AI Analytics ----


@router.post("/insight-reports", response_model=AIInsightReportPublic, status_code=status.HTTP_201_CREATED)
async def generate_insight_report(
    payload: GenerateInsightReportRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.analytics.generate")),
    db: AsyncSession = Depends(get_db),
):
    service = AIAnalyticsService(db)
    report = await service.generate_report(organization_id, generated_by_user_id=user.id, **payload.model_dump())
    return AIInsightReportPublic.model_validate(report)


@router.get("/insight-reports", response_model=dict)
async def list_insight_reports(
    report_type: InsightReportType | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AIAnalyticsService(db)
    reports, total = await service.list_reports(organization_id, report_type=report_type, skip=skip, limit=limit)
    return {
        "items": [AIInsightReportPublic.model_validate(r) for r in reports],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/insight-reports/{report_id}", response_model=AIInsightReportPublic)
async def get_insight_report(
    report_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("ai.analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AIAnalyticsService(db)
    report = await service.get_report(report_id, organization_id)
    return AIInsightReportPublic.model_validate(report)
