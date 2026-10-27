"""
Routes for internship projects. Staff: ``our_internships.view`` / ``our_internships.manage``. Students (``/my-internships``)
are ownership-gated like the rest of My Internship.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.our_internships.access import internship_access
from modules.internship_learning.project_models import InternshipProject, ProjectStatus, SubmissionMethod
from modules.internship_learning.project_schemas import (
    MyProject,
    MyProjectSubmission,
    ProjectCreateRequest,
    ProjectOut,
    ProjectSelectionRow,
    ProjectUpdateRequest,
    ReceivedRequest,
)
from modules.internship_learning.project_service import (
    PROJECT_FILES,
    PROJECT_SUBMISSION_FILES,
    PROJECT_TEMPLATES,
    ProjectService,
)
from modules.internship_learning.review_service import ReviewService
from modules.internship_learning.schemas import FileOut, MessageResponse
from modules.our_internships.service import OurInternshipService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
my_router = APIRouter()

_KINDS = {"document": PROJECT_FILES, "template": PROJECT_TEMPLATES}


async def _out(service: ProjectService, projects: list[InternshipProject]) -> list[ProjectOut]:
    ids = [p.id for p in projects]
    chosen, submitted = await service.counts(ids)
    documents = await service.files.for_owners(PROJECT_FILES, ids)
    templates = await service.files.for_owners(PROJECT_TEMPLATES, ids)
    out = []
    for p in projects:
        item = ProjectOut.model_validate(p)
        item.documents = [FileOut(**service.learning.file_out(f)) for f in documents.get(p.id, [])]
        item.templates = [FileOut(**service.learning.file_out(f)) for f in templates.get(p.id, [])]
        item.chosen_count = chosen.get(p.id, 0)
        item.submitted_count = submitted.get(p.id, 0)
        out.append(item)
    return out


# ============================ staff ============================


@router.get("/{internship_id}/projects", response_model=list[ProjectOut])
async def list_projects(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    await OurInternshipService(db).get(internship_id, organization_id)
    service = ProjectService(db)
    return await _out(service, await service.list_all(internship_id, organization_id))


@router.post("/{internship_id}/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    internship_id: uuid.UUID,
    payload: ProjectCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    internship = await OurInternshipService(db).get(internship_id, organization_id)
    service = ProjectService(db)
    project = await service.create(internship, user.id, payload.model_dump())
    return (await _out(service, [project]))[0]


# fixed paths first, so "selections" is never read as a project id
@router.get("/{internship_id}/project-selections", response_model=list[ProjectSelectionRow])
async def project_selections(
    internship_id: uuid.UUID,
    project_id: uuid.UUID | None = Query(default=None),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    """Which project each enrolled student chose, and what they handed in."""
    await OurInternshipService(db).get(internship_id, organization_id)
    return await ProjectService(db).selection_rows(internship_id, project_id)


@router.get("/{internship_id}/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("view")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    return (await _out(service, [await service.get(internship_id, project_id, organization_id)]))[0]


@router.patch("/{internship_id}/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get(internship_id, project_id, organization_id)
    fields = payload.model_dump(exclude_unset=True)
    for required in ("title", "allow_file", "allow_email", "allow_repository", "max_files", "allow_late", "status", "reference_links"):
        if required in fields and fields[required] is None:
            raise ValidationError(f"{required} cannot be empty.")
    project = await service.update(project, fields)
    return (await _out(service, [project]))[0]


@router.delete("/{internship_id}/projects/{project_id}", response_model=MessageResponse)
async def delete_project(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get(internship_id, project_id, organization_id)
    await service.delete(project)
    return MessageResponse(message="The project, the choices made for it and its submissions were deleted.")


@router.post("/{internship_id}/projects/{project_id}/files", response_model=FileOut, status_code=status.HTTP_201_CREATED)
async def add_project_file(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    kind: str = Query(default="document"),
    file: UploadFile = File(...),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """A project document, or a template students start from (``kind`` = document | template)."""
    if kind not in _KINDS:
        raise ValidationError("kind must be document or template.")
    service = ProjectService(db)
    project = await service.get(internship_id, project_id, organization_id)
    existing = (await service.files.for_owners(_KINDS[kind], [project.id])).get(project.id, [])
    if len(existing) >= 20:
        raise ValidationError("A project can have at most 20 files of each kind.")
    filename, content_type, data = await service.files.read_upload(file)
    record = await service.files.store(
        organization_id=organization_id,
        internship_id=internship_id,
        owner_type=_KINDS[kind],
        owner_id=project.id,
        uploaded_by=user.id,
        filename=filename,
        content_type=content_type,
        data=data,
    )
    return FileOut(**service.learning.file_out(record))


@router.delete("/{internship_id}/projects/{project_id}/files/{file_id}", response_model=MessageResponse)
async def delete_project_file(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get(internship_id, project_id, organization_id)
    for owner_type in (PROJECT_FILES, PROJECT_TEMPLATES):
        try:
            record = await service.files.get(file_id, owner_type, project.id)
        except NotFoundError:
            continue
        await service.files.delete(record)
        return MessageResponse(message="The file was removed.")
    raise NotFoundError("File", file_id)


@router.put("/{internship_id}/projects/{project_id}/submissions/{selection_id}/received", response_model=ProjectSelectionRow)
async def mark_received(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    payload: ReceivedRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(internship_access("manage")),
    db: AsyncSession = Depends(get_db),
):
    """Confirm (or take back) that a student's emailed work arrived."""
    service = ProjectService(db)
    project = await service.get(internship_id, project_id, organization_id)
    await service.set_received(project, selection_id, payload.received, user.id)
    rows = await service.selection_rows(internship_id, project.id)
    return next(r for r in rows if r["selection_id"] == selection_id)


# ============================ the student ============================


async def _my_project(service: ProjectService, project: InternshipProject, selection, choice) -> MyProject:
    item = MyProject.model_validate(project, from_attributes=True)
    documents = (await service.files.for_owners(PROJECT_FILES, [project.id])).get(project.id, [])
    templates = (await service.files.for_owners(PROJECT_TEMPLATES, [project.id])).get(project.id, [])
    item.documents = [FileOut(**service.learning.file_out(f)) for f in documents]
    item.templates = [FileOut(**service.learning.file_out(f)) for f in templates]
    mine = choice is not None and choice.project_id == project.id
    item.chosen_by_me = mine
    if project.capacity is not None:
        item.spots_left = max(0, project.capacity - await service._chosen_count(project.id))
    submission = await service.my_submission(project.id, selection.id) if mine else None
    holds_other = choice is not None and not mine
    other_locked = holds_other and await service.my_submission(choice.project_id, selection.id) is not None
    item.can_choose = (
        project.status == ProjectStatus.PUBLISHED
        and not mine
        and not other_locked
        and (item.spots_left is None or item.spots_left > 0)
    )
    item.can_submit = mine and service.window_open(project) and not (submission and submission.final_published_at)
    if submission:
        files = (await service.files.for_owners(PROJECT_SUBMISSION_FILES, [submission.id])).get(submission.id, [])
        item.submission = MyProjectSubmission(
            method=submission.method,
            repository_url=submission.repository_url,
            note=submission.note,
            submitted_at=submission.submitted_at,
            is_late=submission.is_late,
            files=[FileOut(**service.learning.file_out(f)) for f in files],
            received_at=submission.received_at,
            result=await ReviewService(service.db).result_for_student(project, submission),
        )
    return item


async def _context(db: AsyncSession, student: Student, internship_id: uuid.UUID):
    service = ProjectService(db)
    selection = await service.learning.selection_for_student(student, internship_id)
    return service, selection, await service.my_choice(internship_id, selection.id)


@my_router.get("/{internship_id}/projects", response_model=list[MyProject])
async def my_projects(
    internship_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service, selection, choice = await _context(db, student, internship_id)
    projects = await service.list_all(internship_id, student.organization_id, published_only=True)
    return [await _my_project(service, p, selection, choice) for p in projects]


@my_router.post("/{internship_id}/projects/{project_id}/choose", response_model=MyProject)
async def choose_project(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service, selection, _ = await _context(db, student, internship_id)
    project = await service.get(internship_id, project_id, student.organization_id)
    if project.status == ProjectStatus.DRAFT:
        raise NotFoundError("Project", project_id)
    choice = await service.choose(project, selection)
    return await _my_project(service, project, selection, choice)


@my_router.delete("/{internship_id}/projects/choice", response_model=MessageResponse)
async def drop_choice(
    internship_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service, selection, _ = await _context(db, student, internship_id)
    await service.unchoose(internship_id, selection)
    return MessageResponse(message="You are no longer on a project. You can choose another.")


@my_router.post("/{internship_id}/projects/{project_id}/submission", response_model=MyProject)
async def submit_project(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    method: SubmissionMethod = Form(...),
    repository_url: str | None = Form(default=None),
    note: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_active_user),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service, selection, _ = await _context(db, student, internship_id)
    project = await service.get(internship_id, project_id, student.organization_id)
    if project.status == ProjectStatus.DRAFT:
        raise NotFoundError("Project", project_id)
    if len(files) > project.max_files:
        raise ValidationError(f"You can attach at most {project.max_files} files.")
    uploads = [await service.files.read_upload(f) for f in files]
    await service.submit(project, selection, user.id, method, repository_url, note, uploads)
    return await _my_project(service, project, selection, await service.my_choice(internship_id, selection.id))
