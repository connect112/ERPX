"""
Routes for the learning side of Our Internships.

Staff (``our_internships.view`` / ``our_internships.manage``): an internship's exams and assignments, and marking.
Students (``/my-internships``): ownership-gated -- a student sees only the internships they are enrolled on, and only
their own submissions; no RBAC permission is needed for that.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.internship_learning.models import AssignmentStatus, InternshipAssignment
from modules.internship_learning.schemas import (
    AssignmentCreateRequest,
    AssignmentOut,
    AssignmentUpdateRequest,
    AvailableExam,
    ExamAssignRequest,
    ExamAssignResponse,
    ExamResultRow,
    ExamSummary,
    FileOut,
    GradeRequest,
    MessageResponse,
    MyAssignment,
    MyExam,
    MyInternship,
    MySubmission,
    SubmissionRow,
)
from modules.internship_learning.service import ASSIGNMENT_FILES, SUBMISSION_FILES, InternshipLearningService
from modules.our_internships.models import OurInternship
from modules.our_internships.service import OurInternshipService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id
from modules.workshop_exams.tasks import enqueue_invites

router = APIRouter()
my_router = APIRouter()


async def _internship(db: AsyncSession, internship_id: uuid.UUID, organization_id: uuid.UUID) -> OurInternship:
    return await OurInternshipService(db).get(internship_id, organization_id)


# ============================ staff: exams ============================


@router.get("/{internship_id}/exams", response_model=list[ExamSummary])
async def list_exams(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    await _internship(db, internship_id, organization_id)
    service = InternshipLearningService(db)
    return await service.exam_summaries(await service.exams_of(internship_id, organization_id))


@router.get("/{internship_id}/exams/available", response_model=list[AvailableExam])
async def available_exams(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    await _internship(db, internship_id, organization_id)
    exams = await InternshipLearningService(db).available_exams(organization_id)
    return [AvailableExam(id=e.id, title=e.title, status=e.status.value) for e in exams]


@router.post("/{internship_id}/exams/{exam_id}/link", response_model=MessageResponse)
async def link_exam(
    internship_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    await InternshipLearningService(db).link_exam(internship, exam_id)
    return MessageResponse(message="The exam was added to this internship.")


@router.delete("/{internship_id}/exams/{exam_id}/link", response_model=MessageResponse)
async def unlink_exam(
    internship_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    await InternshipLearningService(db).unlink_exam(internship, exam_id)
    return MessageResponse(message="The exam was removed from this internship. The exam itself was kept.")


@router.post("/{internship_id}/exams/{exam_id}/assign", response_model=ExamAssignResponse)
async def assign_exam(
    internship_id: uuid.UUID,
    exam_id: uuid.UUID,
    payload: ExamAssignRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Put every enrolled student on the exam and, if asked, email each their personal link."""
    internship = await _internship(db, internship_id, organization_id)
    service = InternshipLearningService(db)
    exam = await service.linked_exam(internship, exam_id)
    added, existing, invite_ids = await service.assign_exam(exam, payload.send_invites)
    # Queue only after the rows are committed, so a worker never reads a row that is not there yet.
    await db.commit()
    enqueue_invites(invite_ids)
    return ExamAssignResponse(added=added, already_on_exam=existing, invited=len(invite_ids))


@router.get("/{internship_id}/exams/{exam_id}/results", response_model=list[ExamResultRow])
async def exam_results(
    internship_id: uuid.UUID,
    exam_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    service = InternshipLearningService(db)
    exam = await service.linked_exam(internship, exam_id)
    return await service.exam_results(exam)


# ============================ staff: assignments ============================


async def _assignment_out(service: InternshipLearningService, assignments: list[InternshipAssignment]) -> list[AssignmentOut]:
    counts = await service.submission_counts([a.id for a in assignments])
    files = await service.files.for_owners(ASSIGNMENT_FILES, [a.id for a in assignments])
    enrolled = len(await service.enrolled(assignments[0].internship_id)) if assignments else 0
    out = []
    for a in assignments:
        item = AssignmentOut.model_validate(a)
        item.files = [FileOut(**service.file_out(f)) for f in files.get(a.id, [])]
        item.submitted_count, item.graded_count = counts.get(a.id, (0, 0))
        item.enrolled_count = enrolled
        out.append(item)
    return out


@router.get("/{internship_id}/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    await _internship(db, internship_id, organization_id)
    service = InternshipLearningService(db)
    return await _assignment_out(service, await service.list_assignments(internship_id, organization_id))


@router.post("/{internship_id}/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    internship_id: uuid.UUID,
    payload: AssignmentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await _internship(db, internship_id, organization_id)
    service = InternshipLearningService(db)
    assignment = await service.create_assignment(internship, user.id, payload.model_dump())
    return (await _assignment_out(service, [assignment]))[0]


@router.get("/{internship_id}/assignments/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    assignment = await service.get_assignment(internship_id, assignment_id, organization_id)
    return (await _assignment_out(service, [assignment]))[0]


@router.patch("/{internship_id}/assignments/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: AssignmentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    assignment = await service.get_assignment(internship_id, assignment_id, organization_id)
    fields = payload.model_dump(exclude_unset=True)
    for required in ("title", "tasks", "rubric", "max_marks", "allow_late", "max_files", "status"):
        if required in fields and fields[required] is None:
            raise ValidationError(f"{required} cannot be empty.")
    assignment = await service.update_assignment(assignment, fields)
    return (await _assignment_out(service, [assignment]))[0]


@router.delete("/{internship_id}/assignments/{assignment_id}", response_model=MessageResponse)
async def delete_assignment(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    assignment = await service.get_assignment(internship_id, assignment_id, organization_id)
    await service.delete_assignment(assignment)
    return MessageResponse(message="The assignment and its submissions were deleted.")


@router.post("/{internship_id}/assignments/{assignment_id}/files", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def add_assignment_file(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Reference material the students can download (a brief, a dataset, a template)."""
    service = InternshipLearningService(db)
    assignment = await service.get_assignment(internship_id, assignment_id, organization_id)
    existing = (await service.files.for_owners(ASSIGNMENT_FILES, [assignment.id])).get(assignment.id, [])
    if len(existing) >= 20:
        raise ValidationError("An assignment can have at most 20 reference files.")
    filename, content_type, data = await service.files.read_upload(file)
    record = await service.files.store(
        organization_id=organization_id,
        internship_id=internship_id,
        owner_type=ASSIGNMENT_FILES,
        owner_id=assignment.id,
        uploaded_by=user.id,
        filename=filename,
        content_type=content_type,
        data=data,
    )
    return FileOut(**service.file_out(record))


@router.delete("/{internship_id}/assignments/{assignment_id}/files/{file_id}", response_model=MessageResponse)
async def delete_assignment_file(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    file_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    assignment = await service.get_assignment(internship_id, assignment_id, organization_id)
    record = await service.files.get(file_id, ASSIGNMENT_FILES, assignment.id)
    await service.files.delete(record)
    return MessageResponse(message="The file was removed.")


@router.get("/{internship_id}/assignments/{assignment_id}/submissions", response_model=list[SubmissionRow])
async def list_submissions(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    assignment = await service.get_assignment(internship_id, assignment_id, organization_id)
    return await service.submission_rows(assignment)


@router.put(
    "/{internship_id}/assignments/{assignment_id}/submissions/{selection_id}/grade", response_model=SubmissionRow
)
async def grade_submission(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    selection_id: uuid.UUID,
    payload: GradeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    assignment = await service.get_assignment(internship_id, assignment_id, organization_id)
    await service.grade(assignment, selection_id, payload, user.id)
    return next(r for r in await service.submission_rows(assignment) if r["selection_id"] == selection_id)


# ============================ the student: My Internship ============================


@my_router.get("", response_model=list[MyInternship])
async def my_internships(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from modules.our_internships.models import InternshipSelection, LmsStatus

    rows = await db.execute(
        select(InternshipSelection, OurInternship)
        .join(OurInternship, OurInternship.id == InternshipSelection.internship_id)
        .where(
            InternshipSelection.lms_student_id == student.id,
            InternshipSelection.lms_status == LmsStatus.GRANTED,
            InternshipSelection.organization_id == student.organization_id,
        )
        .order_by(OurInternship.created_at.desc())
    )
    service = InternshipLearningService(db)
    out = []
    for selection, internship in rows.all():
        assignments = await service.list_assignments(internship.id, student.organization_id, published_only=True)
        open_assignments = 0
        for a in assignments:
            if service.can_submit(a, await service.my_submission(a.id, selection.id)):
                open_assignments += 1
        exams = await service.my_exams(internship.id, student.organization_id, student.email or "")
        out.append(
            MyInternship(
                id=internship.id,
                selection_id=selection.id,
                title=internship.title,
                description=internship.description,
                status=internship.status.value,
                open_assignments=open_assignments,
                open_exams=sum(1 for e, a in exams if a.submitted_at is None and e.status.value == "open"),
            )
        )
    return out


@my_router.get("/{internship_id}", response_model=MyInternship)
async def my_internship(
    internship_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    selection = await service.selection_for_student(student, internship_id)
    internship = await OurInternshipService(db).get(internship_id, student.organization_id)
    return MyInternship(
        id=internship.id,
        selection_id=selection.id,
        title=internship.title,
        description=internship.description,
        status=internship.status.value,
    )


@my_router.get("/{internship_id}/exams", response_model=list[MyExam])
async def my_exams(
    internship_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    await service.selection_for_student(student, internship_id)
    out = []
    for exam, attendee in await service.my_exams(internship_id, student.organization_id, student.email or ""):
        state = "submitted" if attendee.submitted_at else "in_progress" if attendee.started_at else "not_started"
        shown = attendee.submitted_at is not None and exam.show_result
        out.append(
            MyExam(
                id=exam.id,
                title=exam.title,
                description=exam.description,
                duration_minutes=exam.duration_minutes,
                status=exam.status.value,
                state=state,
                url=f"{settings.FRONTEND_URL.rstrip('/')}/workshop-exam/{attendee.access_token}",
                score=attendee.score if shown else None,
                total_marks=attendee.total_marks if shown else None,
                submitted_at=attendee.submitted_at,
            )
        )
    return out


def _my_assignment(
    service: InternshipLearningService,
    assignment: InternshipAssignment,
    reference_files: list,
    submission,
    submission_files: list,
) -> MyAssignment:
    item = MyAssignment.model_validate(assignment, from_attributes=True)
    item.files = [FileOut(**service.file_out(f)) for f in reference_files]
    item.can_submit = service.can_submit(assignment, submission)
    if submission:
        item.submission = MySubmission(
            submitted_at=submission.submitted_at,
            is_late=submission.is_late,
            note=submission.note,
            files=[FileOut(**service.file_out(f)) for f in submission_files],
            reviewed=submission.reviewed_at is not None,
            score=float(submission.score) if submission.score is not None else None,
            rubric_scores=submission.rubric_scores,
            feedback=submission.feedback,
            can_resubmit=item.can_submit,
        )
    return item


async def _assignment_for_student(
    service: InternshipLearningService, student: Student, internship_id: uuid.UUID, assignment_id: uuid.UUID
):
    selection = await service.selection_for_student(student, internship_id)
    assignment = await service.get_assignment(internship_id, assignment_id, student.organization_id)
    if assignment.status == AssignmentStatus.DRAFT:
        raise NotFoundError("Assignment", assignment_id)
    return selection, assignment


async def _my_assignment_full(service, assignment, selection) -> MyAssignment:
    reference = (await service.files.for_owners(ASSIGNMENT_FILES, [assignment.id])).get(assignment.id, [])
    submission = await service.my_submission(assignment.id, selection.id)
    sub_files = (
        (await service.files.for_owners(SUBMISSION_FILES, [submission.id])).get(submission.id, []) if submission else []
    )
    return _my_assignment(service, assignment, reference, submission, sub_files)


@my_router.get("/{internship_id}/assignments", response_model=list[MyAssignment])
async def my_assignments(
    internship_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    selection = await service.selection_for_student(student, internship_id)
    assignments = await service.list_assignments(internship_id, student.organization_id, published_only=True)
    return [await _my_assignment_full(service, a, selection) for a in assignments]


@my_router.get("/{internship_id}/assignments/{assignment_id}", response_model=MyAssignment)
async def my_assignment(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = InternshipLearningService(db)
    selection, assignment = await _assignment_for_student(service, student, internship_id, assignment_id)
    return await _my_assignment_full(service, assignment, selection)


@my_router.post("/{internship_id}/assignments/{assignment_id}/submission", response_model=MyAssignment)
async def submit_assignment(
    internship_id: uuid.UUID,
    assignment_id: uuid.UUID,
    note: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_active_user),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Hand in (or replace) work: any new files replace the earlier ones; sending only a note keeps the earlier files."""
    service = InternshipLearningService(db)
    selection, assignment = await _assignment_for_student(service, student, internship_id, assignment_id)
    if len(files) > assignment.max_files:
        raise ValidationError(f"You can attach at most {assignment.max_files} files.")
    uploads = [await service.files.read_upload(f) for f in files]
    await service.submit(assignment, selection, user.id, note, uploads)
    return await _my_assignment_full(service, assignment, selection)


# Projects live beside exams and assignments, under the same prefixes.
from modules.internship_learning import project_routes  # noqa: E402

router.include_router(project_routes.router)
my_router.include_router(project_routes.my_router)

from modules.internship_learning import review_routes  # noqa: E402

router.include_router(review_routes.router)
my_router.include_router(review_routes.my_router)

from modules.internship_learning import certificate_routes  # noqa: E402

router.include_router(certificate_routes.router)
