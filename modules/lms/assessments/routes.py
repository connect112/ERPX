import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.learning.scope import (
    authorize_internship,
    has_permission,
    require_permission,
    student_internship_ids,
)
from modules.lms.assessments.models import Assessment
from modules.lms.assessments.schemas import (
    AssessmentCreateRequest,
    AssessmentPublic,
    AssessmentUpdateRequest,
    AttemptPublic,
    MessageResponse,
    QuestionCreateRequest,
    QuestionStaff,
    QuestionUpdateRequest,
    SaveAnswersRequest,
    StartAttemptRequest,
    SubmitAttemptRequest,
    TakeResult,
    TakeState,
)
from modules.lms.assessments.service import AssessmentService
from modules.students.actor import resolve_actor
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/assessments"
MANAGE = "lms.assessments.manage"
VIEW = "lms.assessments.view"


async def _authorize(db, user, org, course_id, assessment: Assessment | None, level: str, *, internship_id=None, deleting=False):
    """An internship's own assessment is reached through Our Internships access to that internship; a course-wide one through the course
    permission, exactly as before. The course permission never opens an internship's assessment."""
    target = assessment.internship_id if assessment is not None else internship_id
    if target is not None:
        await authorize_internship(db, user, org, target, level, course_id=course_id, deleting=deleting)  # type: ignore[arg-type]
    else:
        await require_permission(db, user, MANAGE if level == "manage" else VIEW)


async def _student_may_take(db: AsyncSession, student: Student, assessment: Assessment) -> None:
    """A student reaches a published assessment of their course, and an internship's own only with a granted selection on that internship."""
    if not assessment.is_published:
        raise NotFoundError("Assessment", assessment.id)
    if assessment.internship_id is not None and assessment.internship_id not in await student_internship_ids(db, student, assessment.course_id):
        raise NotFoundError("Assessment", assessment.id)


@router.post(_PREFIX, response_model=AssessmentPublic, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    course_id: uuid.UUID,
    payload: AssessmentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await _authorize(db, user, organization_id, course_id, None, "manage", internship_id=payload.internship_id)
    service = AssessmentService(db)
    assessment = await service.create_assessment(course_id, organization_id, **payload.model_dump())
    return AssessmentPublic.model_validate(assessment)


@router.get(_PREFIX, response_model=list[AssessmentPublic])
async def list_assessments(
    course_id: uuid.UUID,
    internship_id: uuid.UUID | None = Query(default=None, description="One internship's own assessments (and, with include_course, the course-wide ones)"),
    include_course: bool = False,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    student = await StudentRepository(db).get_by_user_id(user.id)
    can_view_course = await has_permission(db, user, VIEW)
    if student is not None and not await has_permission(db, user, MANAGE):
        if not can_view_course:
            raise AuthorizationError(f"This action requires the following permission(s): {VIEW}")
        assessments = await service.list_for_student(course_id, student, await student_internship_ids(db, student, course_id))
    elif internship_id is not None:
        # an internship's own assessments are reached through Our Internships access to that internship (an instructor needs no course
        # permission); the course-wide ones beside them only with the course permission
        await authorize_internship(db, user, organization_id, internship_id, "view", course_id=course_id)
        assessments = await service.list_assessments(course_id, organization_id, internship_id=internship_id, include_course=include_course and can_view_course)
    else:
        if not can_view_course:
            raise AuthorizationError(f"This action requires the following permission(s): {VIEW}")
        assessments = await service.list_assessments(course_id, organization_id, internship_id=None, include_course=include_course)
    return [AssessmentPublic.model_validate(a) for a in assessments]


@router.get(_PREFIX + "/{assessment_id}", response_model=AssessmentPublic)
async def get_assessment(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    student = await StudentRepository(db).get_by_user_id(user.id)
    if student is not None and not await has_permission(db, user, MANAGE):
        await require_permission(db, user, VIEW)
        await _student_may_take(db, student, assessment)
    else:
        await _authorize(db, user, organization_id, course_id, assessment, "view")
    return AssessmentPublic.model_validate(assessment)


@router.patch(_PREFIX + "/{assessment_id}", response_model=AssessmentPublic)
async def update_assessment(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: AssessmentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    await _authorize(db, user, organization_id, course_id, assessment, "manage")
    updated = await service.update_assessment(assessment_id, course_id, organization_id, **payload.model_dump(exclude_unset=True))
    return AssessmentPublic.model_validate(updated)


@router.delete(_PREFIX + "/{assessment_id}", response_model=MessageResponse)
async def delete_assessment(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    await _authorize(db, user, organization_id, course_id, assessment, "manage", deleting=True)
    await service.delete_assessment(assessment_id, course_id, organization_id)
    return MessageResponse(message="Assessment deleted successfully.")


# ------------------------------------------------------------------ questions (staff only: they show the correct answers)


@router.get(_PREFIX + "/{assessment_id}/questions", response_model=list[QuestionStaff])
async def list_questions(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    await _authorize(db, user, organization_id, course_id, assessment, "manage")
    return [QuestionStaff.model_validate(q) for q in await service.questions(assessment_id)]


@router.post(_PREFIX + "/{assessment_id}/questions", response_model=QuestionStaff, status_code=status.HTTP_201_CREATED)
async def add_question(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: QuestionCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    await _authorize(db, user, organization_id, course_id, assessment, "manage")
    return QuestionStaff.model_validate(await service.add_question(assessment, **payload.model_dump()))


@router.put(_PREFIX + "/{assessment_id}/questions/{question_id}", response_model=QuestionStaff)
async def update_question(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: QuestionUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    await _authorize(db, user, organization_id, course_id, assessment, "manage")
    return QuestionStaff.model_validate(await service.update_question(assessment, question_id, **payload.model_dump()))


@router.delete(_PREFIX + "/{assessment_id}/questions/{question_id}", response_model=MessageResponse)
async def delete_question(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    question_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    await _authorize(db, user, organization_id, course_id, assessment, "manage", deleting=True)
    await service.delete_question(assessment, question_id)
    return MessageResponse(message="Question removed.")


# ------------------------------------------------------------------ taking it (a student, always as themselves)


@router.post(_PREFIX + "/{assessment_id}/take/start", response_model=TakeState)
async def take_start(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    user: User = Depends(require_permissions("lms.assessments.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, student.organization_id)
    await _student_may_take(db, student, assessment)
    return TakeState(**await service.take_start(assessment, student))


@router.put(_PREFIX + "/{assessment_id}/take/answers", response_model=MessageResponse)
async def take_save(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: SaveAnswersRequest,
    student: Student = Depends(get_current_student),
    user: User = Depends(require_permissions("lms.assessments.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, student.organization_id)
    await _student_may_take(db, student, assessment)
    await service.take_save(assessment, student, payload.answers)
    return MessageResponse(message="Saved.")


@router.post(_PREFIX + "/{assessment_id}/take/submit", response_model=TakeResult)
async def take_submit(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: SaveAnswersRequest,
    student: Student = Depends(get_current_student),
    user: User = Depends(require_permissions("lms.assessments.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, student.organization_id)
    await _student_may_take(db, student, assessment)
    await service.take_submit(assessment, student, payload.answers)
    return TakeResult(**(await service.my_result(assessment, student) or {}))


@router.get(_PREFIX + "/{assessment_id}/take/result", response_model=TakeResult | None)
async def take_result(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    user: User = Depends(require_permissions("lms.assessments.attempt")),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, student.organization_id)
    await _student_may_take(db, student, assessment)
    result = await service.my_result(assessment, student)
    return TakeResult(**result) if result else None


# ------------------------------------------------------------------ recording by staff


@router.post(_PREFIX + "/{assessment_id}/attempts", response_model=AttemptPublic, status_code=status.HTTP_201_CREATED)
async def start_attempt(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    payload: StartAttemptRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    actor = await resolve_actor(db, user, organization_id, payload.student_id, {MANAGE})
    if actor.user_id == user.id:
        await require_permission(db, user, "lms.assessments.attempt")  # a student attempting as themselves needs the student permission
        await _student_may_take(db, actor, assessment)  # as themselves: only what a student may reach
    else:
        await _authorize(db, user, organization_id, course_id, assessment, "manage")
        if assessment.internship_id is not None and assessment.internship_id not in await student_internship_ids(db, actor, course_id):
            raise NotFoundError("Student", actor.id)
    attempt = await service.start_attempt(assessment_id, course_id, organization_id, actor)
    return AttemptPublic.model_validate(attempt)


@router.post(_PREFIX + "/{assessment_id}/attempts/{attempt_id}/submit", response_model=AttemptPublic)
async def submit_attempt(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: SubmitAttemptRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """A score entered by hand: staff only (never a student), and only for an assessment that has no questions."""
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    await _authorize(db, user, organization_id, course_id, assessment, "manage")
    attempt = await service.submit_attempt(attempt_id, assessment_id, course_id, organization_id, payload.score)
    return AttemptPublic.model_validate(attempt)


@router.get(_PREFIX + "/{assessment_id}/attempts", response_model=list[AttemptPublic])
async def list_attempts(
    course_id: uuid.UUID,
    assessment_id: uuid.UUID,
    internship_id: uuid.UUID | None = Query(default=None, description="Only this internship's students"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssessmentService(db)
    assessment = await service.get_assessment(assessment_id, course_id, organization_id)
    if internship_id is not None:
        if assessment.internship_id not in (None, internship_id):
            raise NotFoundError("Assessment", assessment_id)
        await authorize_internship(db, user, organization_id, internship_id, "view", course_id=course_id)
    else:
        await _authorize(db, user, organization_id, course_id, assessment, "view")
    rows = await service.list_attempts(assessment_id, course_id, organization_id, internship_id=internship_id or assessment.internship_id)
    return [AttemptPublic(**r) for r in rows]
