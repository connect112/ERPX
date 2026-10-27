"""
Internship projects -- staff create them, enrolled students choose one and hand it in.

A student holds one project per internship. They may change their choice until they have handed something in. How the
work may be handed in (files, an email, a repository link) is decided per project.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.internship_learning.files import FileService
from modules.internship_learning.project_models import (
    InternshipProject,
    ProjectChoice,
    ProjectReview,
    ProjectStatus,
    ProjectSubmission,
    SubmissionMethod,
)
from modules.internship_learning.project_schemas import clean_url
from modules.internship_learning.service import InternshipLearningService
from modules.our_internships.models import InternshipSelection, OurInternship

PROJECT_FILES = "project"
PROJECT_TEMPLATES = "project_template"
PROJECT_SUBMISSION_FILES = "project_submission"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.files = FileService(db)
        self.learning = InternshipLearningService(db)

    # ---------------- staff ----------------

    async def get(self, internship_id: uuid.UUID, project_id: uuid.UUID, organization_id: uuid.UUID) -> InternshipProject:
        project = (
            await self.db.execute(
                select(InternshipProject).where(
                    InternshipProject.id == project_id,
                    InternshipProject.internship_id == internship_id,
                    InternshipProject.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)
        return project

    async def list_all(
        self, internship_id: uuid.UUID, organization_id: uuid.UUID, *, published_only: bool = False
    ) -> list[InternshipProject]:
        query = select(InternshipProject).where(
            InternshipProject.internship_id == internship_id, InternshipProject.organization_id == organization_id
        )
        if published_only:
            query = query.where(InternshipProject.status != ProjectStatus.DRAFT)
        return list((await self.db.execute(query.order_by(InternshipProject.created_at.desc()))).scalars().all())

    def _check(self, fields: dict) -> dict:
        fields = dict(fields)
        if "reference_links" in fields and fields["reference_links"] is not None:
            links = [dict(link) for link in fields["reference_links"]]
            if len({link["id"] for link in links}) != len(links):
                raise ValidationError("Two reference links share the same id.")
            fields["reference_links"] = links
        if "review_factors" in fields and fields["review_factors"] is not None:
            factors = [dict(f) for f in fields["review_factors"]]
            if len({f["id"] for f in factors}) != len(factors):
                raise ValidationError("Two review factors share the same id.")
            fields["review_factors"] = factors
            if factors:
                # With factors the marks come from them, so the total is always what they add up to.
                fields["max_marks"] = sum(f["max_marks"] for f in factors)
        starts, deadline = fields.get("starts_at"), fields.get("deadline_at")
        if starts and deadline and deadline <= starts:
            raise ValidationError("The deadline must be after the start time.")
        return fields

    @staticmethod
    def _assert_methods(project: InternshipProject) -> None:
        if not (project.allow_file or project.allow_email or project.allow_repository):
            raise ValidationError("Allow at least one way of submitting: files, email or a repository link.")
        if project.allow_email and not project.submission_email:
            raise ValidationError("Enter the email address students should send their work to.")

    async def create(self, internship: OurInternship, user_id: uuid.UUID, fields: dict) -> InternshipProject:
        project = InternshipProject(
            organization_id=internship.organization_id,
            internship_id=internship.id,
            created_by_user_id=user_id,
            **self._check(fields),
        )
        self._assert_methods(project)
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def update(self, project: InternshipProject, fields: dict) -> InternshipProject:
        fields = self._check(fields)
        if "deadline_at" in fields or "starts_at" in fields:
            starts = fields.get("starts_at", project.starts_at)
            deadline = fields.get("deadline_at", project.deadline_at)
            if starts and deadline and deadline <= starts:
                raise ValidationError("The deadline must be after the start time.")
        if ("review_factors" in fields and fields["review_factors"] != project.review_factors) or (
            "max_marks" in fields and fields["max_marks"] != project.max_marks
        ):
            reviewed = (
                await self.db.execute(
                    select(func.count())
                    .select_from(ProjectReview)
                    .join(ProjectSubmission, ProjectSubmission.id == ProjectReview.submission_id)
                    .where(ProjectSubmission.project_id == project.id)
                )
            ).scalar_one()
            if reviewed:
                raise ConflictError("The review factors and total marks cannot be changed once reviews have been written.")
        if fields.get("capacity") is not None:
            chosen = await self._chosen_count(project.id)
            if fields["capacity"] < chosen:
                raise ConflictError(f"{chosen} students have already chosen this project, so the limit cannot be lower.")
        for key, value in fields.items():
            setattr(project, key, value)
        self._assert_methods(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def delete(self, project: InternshipProject) -> None:
        submissions = (
            (await self.db.execute(select(ProjectSubmission.id).where(ProjectSubmission.project_id == project.id)))
            .scalars()
            .all()
        )
        for submission_id in submissions:
            await self.files.delete_all(PROJECT_SUBMISSION_FILES, submission_id)
        await self.db.execute(delete(ProjectReview).where(ProjectReview.submission_id.in_(list(submissions) or [uuid.uuid4()])))
        await self.files.delete_all(PROJECT_FILES, project.id)
        await self.files.delete_all(PROJECT_TEMPLATES, project.id)
        await self.db.delete(project)
        await self.db.flush()

    async def _chosen_count(self, project_id: uuid.UUID) -> int:
        return (
            await self.db.execute(select(func.count()).select_from(ProjectChoice).where(ProjectChoice.project_id == project_id))
        ).scalar_one()

    async def counts(self, project_ids: list[uuid.UUID]) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        if not project_ids:
            return {}, {}
        chosen = dict(
            (
                await self.db.execute(
                    select(ProjectChoice.project_id, func.count())
                    .where(ProjectChoice.project_id.in_(project_ids))
                    .group_by(ProjectChoice.project_id)
                )
            ).all()
        )
        submitted = dict(
            (
                await self.db.execute(
                    select(ProjectSubmission.project_id, func.count())
                    .where(ProjectSubmission.project_id.in_(project_ids))
                    .group_by(ProjectSubmission.project_id)
                )
            ).all()
        )
        return chosen, submitted

    async def selection_rows(self, internship_id: uuid.UUID, only_project: uuid.UUID | None = None) -> list[dict]:
        """Every enrolled student with the project they chose and what they handed in."""
        enrolled = await self.learning.enrolled(internship_id)
        choices = {
            c.selection_id: c
            for c in (await self.db.execute(select(ProjectChoice).where(ProjectChoice.internship_id == internship_id))).scalars()
        }
        projects = {
            p.id: p
            for p in (
                await self.db.execute(select(InternshipProject).where(InternshipProject.internship_id == internship_id))
            ).scalars()
        }
        submissions = {
            (s.project_id, s.selection_id): s
            for s in (
                await self.db.execute(
                    select(ProjectSubmission).where(ProjectSubmission.project_id.in_(list(projects) or [uuid.uuid4()]))
                )
            ).scalars()
        }
        files = await self.files.for_owners(PROJECT_SUBMISSION_FILES, [s.id for s in submissions.values()])
        rows = []
        for selection, person in enrolled:
            choice = choices.get(selection.id)
            if only_project is not None and (choice is None or choice.project_id != only_project):
                continue
            project = projects.get(choice.project_id) if choice else None
            sub = submissions.get((choice.project_id, selection.id)) if choice else None
            rows.append(
                {
                    "selection_id": selection.id,
                    "student_name": person.name,
                    "student_email": person.email,
                    "project_id": project.id if project else None,
                    "project_title": project.title if project else None,
                    "chosen_at": choice.chosen_at if choice else None,
                    "submitted": sub is not None,
                    "method": sub.method if sub else None,
                    "submitted_at": sub.submitted_at if sub else None,
                    "is_late": sub.is_late if sub else False,
                    "resubmission_count": sub.resubmission_count if sub else 0,
                    "repository_url": sub.repository_url if sub else None,
                    "note": sub.note if sub else None,
                    "files": [self.learning.file_out(f) for f in files.get(sub.id, [])] if sub else [],
                    "received_at": sub.received_at if sub else None,
                }
            )
        return rows

    async def set_received(
        self, project: InternshipProject, selection_id: uuid.UUID, received: bool, user_id: uuid.UUID
    ) -> None:
        submission = await self._submission(project.id, selection_id)
        if not submission:
            raise NotFoundError("Submission", selection_id)
        if submission.method != SubmissionMethod.EMAIL:
            raise ValidationError("Only submissions sent by email need to be confirmed as received.")
        submission.received_at = _now() if received else None
        submission.received_by_user_id = user_id if received else None
        await self.db.flush()

    async def _submission(self, project_id: uuid.UUID, selection_id: uuid.UUID) -> ProjectSubmission | None:
        return (
            await self.db.execute(
                select(ProjectSubmission).where(
                    ProjectSubmission.project_id == project_id, ProjectSubmission.selection_id == selection_id
                )
            )
        ).scalar_one_or_none()

    # ---------------- the student ----------------

    async def my_choice(self, internship_id: uuid.UUID, selection_id: uuid.UUID) -> ProjectChoice | None:
        return (
            await self.db.execute(
                select(ProjectChoice).where(
                    ProjectChoice.internship_id == internship_id, ProjectChoice.selection_id == selection_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    def window_open(project: InternshipProject, now: datetime | None = None) -> bool:
        now = now or _now()
        if project.status != ProjectStatus.PUBLISHED:
            return False
        if project.starts_at and now < project.starts_at:
            return False
        return not (project.deadline_at and now > project.deadline_at and not project.allow_late)

    async def choose(self, project: InternshipProject, selection: InternshipSelection) -> ProjectChoice:
        if project.status != ProjectStatus.PUBLISHED:
            raise ValidationError("This project is not open for selection.")
        # Lock the project row so two students taking the last place cannot both succeed.
        await self.db.execute(select(InternshipProject.id).where(InternshipProject.id == project.id).with_for_update())
        current = await self.my_choice(project.internship_id, selection.id)
        if current and current.project_id == project.id:
            return current
        if current and await self._submission(current.project_id, selection.id):
            raise ValidationError("You have already handed in work for your project, so you cannot switch to another.")
        if project.capacity is not None and await self._chosen_count(project.id) >= project.capacity:
            raise ValidationError("This project is full.")
        if current:
            current.project_id = project.id
            current.chosen_at = _now()
            await self.db.flush()
            return current
        choice = ProjectChoice(
            organization_id=project.organization_id,
            internship_id=project.internship_id,
            project_id=project.id,
            selection_id=selection.id,
            chosen_at=_now(),
        )
        self.db.add(choice)
        await self.db.flush()
        return choice

    async def unchoose(self, internship_id: uuid.UUID, selection: InternshipSelection) -> None:
        current = await self.my_choice(internship_id, selection.id)
        if not current:
            return
        if await self._submission(current.project_id, selection.id):
            raise ValidationError("You have already handed in work for your project, so you cannot drop it.")
        await self.db.delete(current)
        await self.db.flush()

    async def submit(
        self,
        project: InternshipProject,
        selection: InternshipSelection,
        user_id: uuid.UUID,
        method: SubmissionMethod,
        repository_url: str | None,
        note: str | None,
        uploads: list[tuple[str, str, bytes]],
    ) -> ProjectSubmission:
        choice = await self.my_choice(project.internship_id, selection.id)
        if not choice or choice.project_id != project.id:
            raise ValidationError("Choose this project before handing in work for it.")
        now = _now()
        if project.status != ProjectStatus.PUBLISHED:
            raise ValidationError("This project is not open for submissions.")
        if project.starts_at and now < project.starts_at:
            raise ValidationError("This project has not opened yet.")
        late = bool(project.deadline_at and now > project.deadline_at)
        if late and not project.allow_late:
            raise ValidationError("The deadline for this project has passed.")
        allowed = {
            SubmissionMethod.FILE: project.allow_file,
            SubmissionMethod.EMAIL: project.allow_email,
            SubmissionMethod.REPOSITORY: project.allow_repository,
        }
        if not allowed[method]:
            raise ValidationError("This project does not accept that way of submitting.")
        existing = await self._submission(project.id, selection.id)
        if existing and existing.final_published_at:
            raise ValidationError("Your result has been published, so this submission can no longer be changed.")
        kept = (
            (await self.files.for_owners(PROJECT_SUBMISSION_FILES, [existing.id])).get(existing.id, []) if existing else []
        )
        clean_note = (note or "").strip()[:8000] or None
        repo = None
        if method == SubmissionMethod.FILE:
            total = len(uploads) if uploads else len(kept)
            if total == 0:
                raise ValidationError("Please attach at least one file.")
            if total > project.max_files:
                raise ValidationError(f"You can attach at most {project.max_files} files.")
        elif method == SubmissionMethod.REPOSITORY:
            try:
                repo = clean_url(repository_url or "")
            except ValueError as exc:
                raise ValidationError(str(exc)) from None
            if len(repo) > 500:
                raise ValidationError("That repository link is too long.")
        elif not clean_note:
            raise ValidationError("Write when and from which address you sent the email.")
        if existing:
            existing.method = method
            existing.repository_url = repo
            existing.note = clean_note
            existing.submitted_at = now
            existing.is_late = late
            existing.resubmission_count += 1
            existing.received_at = None
            existing.received_by_user_id = None
            submission = existing
        else:
            submission = ProjectSubmission(
                organization_id=project.organization_id,
                project_id=project.id,
                selection_id=selection.id,
                method=method,
                repository_url=repo,
                note=clean_note,
                submitted_at=now,
                is_late=late,
            )
            self.db.add(submission)
        await self.db.flush()
        if method != SubmissionMethod.FILE:
            for old in kept:
                await self.files.delete(old)
        elif uploads:
            for filename, content_type, data in uploads:
                await self.files.store(
                    organization_id=project.organization_id,
                    internship_id=project.internship_id,
                    owner_type=PROJECT_SUBMISSION_FILES,
                    owner_id=submission.id,
                    uploaded_by=user_id,
                    filename=filename,
                    content_type=content_type,
                    data=data,
                )
            for old in kept:
                await self.files.delete(old)
        return submission

    async def my_submission(self, project_id: uuid.UUID, selection_id: uuid.UUID) -> ProjectSubmission | None:
        return await self._submission(project_id, selection_id)
