import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.lms.assessments.schemas import (
    AssessmentCreateRequest,
    AssessmentPublic,
    AssessmentUpdateRequest,
    AttemptPublic,
    MessageResponse,
    StartAttemptRequest,
    SubmitAttemptRequest,
)
from modules.lms.assessments.service import AssessmentService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/assessments"


@router.post(_PREFIX, response_model=AssessmentPublic, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    course_id: uuid.UUID,
    payload: AssessmentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.create_assessment(course_id, organization_id, **payload.model_dump())
    return AssessmentPublic.model_validate(assessment)


@router.get(_PREFIX, response_model=list[AssessmentPublic])
async def list_assessments(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessments = await service.list_assessments(course_id, organization_id)
    return [AssessmentPublic.model_validate(a) for a in assessments]


@router.get(_PREFIX + "/{assessment_id}", response_model=AssessmentPublic)
async def get_assessment(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    return AssessmentPublic.model_validate(assessment)


@router.patch(_PREFIX + "/{assessment_id}", response_model=AssessmentPublic)
async def update_assessment(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: AssessmentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.update_assessment(
        assessment_id, course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AssessmentPublic.model_validate(assessment)


@router.delete(_PREFIX + "/{assessment_id}", response_model=MessageResponse)
async def delete_assessment(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    await service.delete_assessment(assessment_id, course_id, organization_id)
    return MessageResponse(message="Assessment deleted successfully.")


@router.post(_PREFIX + "/{assessment_id}/attempts", response_model=AttemptPublic, status_code=status.HTTP_201_CREATED)
async def start_attempt(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: StartAttemptRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    attempt = await service.start_attempt(assessment_id, course_id, organization_id, payload.student_id)
    return AttemptPublic.model_validate(attempt)


@router.post(_PREFIX + "/{assessment_id}/attempts/{attempt_id}/submit", response_model=AttemptPublic)
async def submit_attempt(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: SubmitAttemptRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    attempt = await service.submit_attempt(
        attempt_id, assessment_id, course_id, organization_id, payload.score
    )
    return AttemptPublic.model_validate(attempt)


@router.get(_PREFIX + "/{assessment_id}/attempts", response_model=list[AttemptPublic])
async def list_attempts(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assessments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    attempts = await service.list_attempts(assessment_id, course_id, organization_id)
    return [AttemptPublic.model_validate(a) for a in attempts]
