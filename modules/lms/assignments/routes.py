import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.batches.repository import BatchRepository
from modules.lms.assignments.schemas import (
    AssignmentCreateRequest,
    AssignmentPublic,
    AssignmentUpdateRequest,
    MessageResponse,
    SubmissionCreateRequest,
    SubmissionGradeRequest,
    SubmissionPublic,
    SubmissionWithStudentPublic,
)
from modules.lms.assignments.service import AssignmentService
from modules.students.repository import StudentRepository
from modules.trainers.dependencies import get_current_trainer
from modules.trainers.models import Trainer
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_PREFIX = "/courses/{course_id}/assignments"


async def _require_teaches_course(
    course_id: uuid.UUID, trainer: Trainer, db: AsyncSession
) -> None:
    teaches = await BatchRepository(db).trainer_teaches_course(trainer.id, course_id)
    if not teaches:
        raise AuthorizationError("You do not teach this course.")


@router.post(_PREFIX, response_model=AssignmentPublic, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    course_id: uuid.UUID,
    payload: AssignmentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    assignment = await service.create_assignment(course_id, organization_id, **payload.model_dump())
    return AssignmentPublic.model_validate(assignment)


@router.get(_PREFIX, response_model=list[AssignmentPublic])
async def list_assignments(
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    assignments = await service.list_assignments(course_id, organization_id)
    return [AssignmentPublic.model_validate(a) for a in assignments]


@router.get(_PREFIX + "/me", response_model=list[AssignmentPublic])
async def list_my_course_assignments(
    course_id: uuid.UUID,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    await _require_teaches_course(course_id, trainer, db)
    service = AssignmentService(db)
    assignments = await service.list_assignments(course_id, trainer.organization_id)
    return [AssignmentPublic.model_validate(a) for a in assignments]


@router.get(_PREFIX + "/{assignment_id}", response_model=AssignmentPublic)
async def get_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    assignment = await service.get_assignment(assignment_id, course_id, organization_id)
    return AssignmentPublic.model_validate(assignment)


@router.patch(_PREFIX + "/{assignment_id}", response_model=AssignmentPublic)
async def update_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: AssignmentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    assignment = await service.update_assignment(
        assignment_id, course_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AssignmentPublic.model_validate(assignment)


@router.delete(_PREFIX + "/{assignment_id}", response_model=MessageResponse)
async def delete_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    await service.delete_assignment(assignment_id, course_id, organization_id)
    return MessageResponse(message="Assignment deleted successfully.")


@router.post(
    _PREFIX + "/{assignment_id}/submissions",
    response_model=SubmissionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def submit_assignment(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: SubmissionCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.submit")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    submission = await service.submit(
        assignment_id,
        course_id,
        organization_id,
        payload.student_id,
        payload.content_url,
        payload.content_text,
    )
    return SubmissionPublic.model_validate(submission)


@router.get(_PREFIX + "/{assignment_id}/submissions", response_model=list[SubmissionPublic])
async def list_submissions(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    submissions = await service.list_submissions(assignment_id, course_id, organization_id)
    return [SubmissionPublic.model_validate(s) for s in submissions]


@router.post(
    _PREFIX + "/{assignment_id}/submissions/{submission_id}/grade", response_model=SubmissionPublic
)
async def grade_submission(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_id: uuid.UUID,
    payload: SubmissionGradeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("lms.assignments.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AssignmentService(db)
    submission = await service.grade_submission(
        submission_id, assignment_id, course_id, organization_id, payload.score, payload.feedback
    )
    return SubmissionPublic.model_validate(submission)


@router.get(
    _PREFIX + "/{assignment_id}/submissions/me", response_model=list[SubmissionWithStudentPublic]
)
async def list_my_course_submissions(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    await _require_teaches_course(course_id, trainer, db)
    service = AssignmentService(db)
    submissions = await service.list_submissions(assignment_id, course_id, trainer.organization_id)

    student_repo = StudentRepository(db)
    student_names: dict = {}
    results = []
    for submission in submissions:
        if submission.student_id not in student_names:
            student = await student_repo.get_by_id(submission.student_id, trainer.organization_id)
            student_names[submission.student_id] = student.full_name if student else "Unknown student"
        results.append(
            SubmissionWithStudentPublic(
                **SubmissionPublic.model_validate(submission).model_dump(),
                student_name=student_names[submission.student_id],
            )
        )
    return results


@router.post(
    _PREFIX + "/{assignment_id}/submissions/{submission_id}/grade/me",
    response_model=SubmissionPublic,
)
async def grade_my_course_submission(
    course_id: uuid.UUID,
    assignment_id: uuid.UUID,
    submission_id: uuid.UUID,
    payload: SubmissionGradeRequest,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    await _require_teaches_course(course_id, trainer, db)
    service = AssignmentService(db)
    submission = await service.grade_submission(
        submission_id, assignment_id, course_id, trainer.organization_id, payload.score, payload.feedback
    )
    return SubmissionPublic.model_validate(submission)
