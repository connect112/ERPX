import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.ai.models import (
    ConversationType,
    InsightReportType,
    InterviewSessionStatus,
    MessageRole,
)
from modules.examinations.question_bank.models import Difficulty, QuestionType


# ---- AI Tutor / Chat Assistant ----


class StartConversationRequest(BaseModel):
    conversation_type: ConversationType
    student_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=255)


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


class MessagePublic(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    initiated_by_user_id: uuid.UUID
    student_id: uuid.UUID | None
    course_id: uuid.UUID | None
    conversation_type: ConversationType
    title: str | None
    is_archived: bool
    created_at: datetime
    messages: list[MessagePublic] = []

    model_config = {"from_attributes": True}


# ---- AI Question Generator ----


class GenerateQuestionsRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=255)
    course_id: uuid.UUID | None = None
    question_type: QuestionType
    difficulty: Difficulty
    count: int = Field(default=5, ge=1, le=20)


class GeneratedQuestionItemPublic(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    imported_question_id: uuid.UUID | None
    question_text: str
    options: list | None
    correct_answer: str | None
    explanation: str | None
    is_approved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratedQuestionBatchPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    requested_by_user_id: uuid.UUID | None
    course_id: uuid.UUID | None
    topic: str
    question_type: QuestionType
    difficulty: Difficulty
    requested_count: int
    created_at: datetime
    items: list[GeneratedQuestionItemPublic] = []

    model_config = {"from_attributes": True}


class ApproveQuestionItemRequest(BaseModel):
    default_marks: int = Field(default=1, ge=1)


class ReviewQuestionItemRequest(BaseModel):
    question_text: str | None = None
    options: list | None = None
    correct_answer: str | None = None


# ---- AI Resume Builder ----


class GenerateResumeRequest(BaseModel):
    student_id: uuid.UUID
    target_role: str | None = Field(default=None, max_length=150)
    education_summary: str = Field(..., min_length=2)
    skills_summary: str = Field(..., min_length=2)
    experience_summary: str | None = None
    projects_summary: str | None = None


class GeneratedResumePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    student_id: uuid.UUID
    target_role: str | None
    input_summary: str
    content: str
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- AI Interview Simulator ----


class StartInterviewRequest(BaseModel):
    student_id: uuid.UUID
    role_or_topic: str = Field(..., min_length=2, max_length=255)


class SubmitInterviewAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)


class InterviewExchangePublic(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    order_index: int
    question_text: str
    student_answer: str | None
    ai_feedback: str | None
    score_out_of_10: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewSessionPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    student_id: uuid.UUID
    role_or_topic: str
    status: InterviewSessionStatus
    overall_feedback: str | None
    overall_score: float | None
    created_at: datetime
    exchanges: list[InterviewExchangePublic] = []

    model_config = {"from_attributes": True}


# ---- AI Assignment Evaluation ----


class EvaluateSubmissionRequest(BaseModel):
    reference_type: str = Field(..., min_length=1, max_length=50)
    reference_id: uuid.UUID
    submission_text: str = Field(..., min_length=1)
    rubric_text: str | None = None


class AIEvaluationResultPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    evaluated_by_user_id: uuid.UUID | None
    reference_type: str
    reference_id: uuid.UUID
    score_out_of_100: float | None
    feedback: str
    strengths: str | None
    improvement_areas: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- AI Course Recommendation ----


class RecommendCoursesRequest(BaseModel):
    student_id: uuid.UUID
    stated_interests: str | None = None


class CourseRecommendationItem(BaseModel):
    course_id: uuid.UUID
    course_name: str
    reason: str


class CourseRecommendationResponse(BaseModel):
    student_id: uuid.UUID
    recommendations: list[CourseRecommendationItem]


# ---- AI Analytics ----


class GenerateInsightReportRequest(BaseModel):
    report_type: InsightReportType
    reference_id: uuid.UUID | None = None


class AIInsightReportPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    generated_by_user_id: uuid.UUID | None
    report_type: InsightReportType
    reference_id: uuid.UUID | None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
