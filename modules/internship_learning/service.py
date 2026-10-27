"""
Internship learning -- exams and assignments for the students enrolled on an internship.

"Enrolled" always means a student on the internship's shortlist who has been given LMS access (``lms_status`` granted);
that is the group assignments are marked for and exams are assigned to, and the only one that can see this work.
"""

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.institutions.models import InstitutionStudent
from modules.internship_learning.files import FileService
from modules.internship_learning.models import AssignmentStatus, AssignmentSubmission, InternshipAssignment
from modules.internship_learning.schemas import GradeRequest
from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship
from modules.students.models import Student
from modules.workshop_exams.models import (
    WorkshopExam,
    WorkshopExamAttendee,
    WorkshopExamQuestion,
    WorkshopExamStatus,
)

ASSIGNMENT_FILES = "assignment"
SUBMISSION_FILES = "assignment_submission"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_tasks(tasks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    for task in tasks:
        if task["id"] in seen:
            raise ValidationError("Two tasks share the same id.")
        seen.add(task["id"])
    return tasks


def _clean_rubric(rubric: list[dict]) -> list[dict]:
    seen: set[str] = set()
    for rule in rubric:
        if rule["id"] in seen:
            raise ValidationError("Two rubric criteria share the same id.")
        seen.add(rule["id"])
    return rubric


class InternshipLearningService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.files = FileService(db)

    # ---------------- who is enrolled ----------------

    async def enrolled(self, internship_id: uuid.UUID) -> list[tuple[InternshipSelection, InstitutionStudent]]:
        rows = await self.db.execute(
            select(InternshipSelection, InstitutionStudent)
            .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
            .where(
                InternshipSelection.internship_id == internship_id,
                InternshipSelection.lms_status == LmsStatus.GRANTED,
            )
            .order_by(InstitutionStudent.name)
        )
        return [(s, p) for s, p in rows.all()]

    async def selection_for_student(self, student: Student, internship_id: uuid.UUID) -> InternshipSelection:
        selection = (
            await self.db.execute(
                select(InternshipSelection).where(
                    InternshipSelection.internship_id == internship_id,
                    InternshipSelection.lms_student_id == student.id,
                    InternshipSelection.lms_status == LmsStatus.GRANTED,
                    InternshipSelection.organization_id == student.organization_id,
                )
            )
        ).scalar_one_or_none()
        if not selection:
            raise NotFoundError("Internship", internship_id)
        return selection

    # ---------------- assignments: staff ----------------

    async def get_assignment(
        self, internship_id: uuid.UUID, assignment_id: uuid.UUID, organization_id: uuid.UUID
    ) -> InternshipAssignment:
        assignment = (
            await self.db.execute(
                select(InternshipAssignment).where(
                    InternshipAssignment.id == assignment_id,
                    InternshipAssignment.internship_id == internship_id,
                    InternshipAssignment.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if not assignment:
            raise NotFoundError("Assignment", assignment_id)
        return assignment

    async def list_assignments(
        self, internship_id: uuid.UUID, organization_id: uuid.UUID, *, published_only: bool = False
    ) -> list[InternshipAssignment]:
        query = select(InternshipAssignment).where(
            InternshipAssignment.internship_id == internship_id,
            InternshipAssignment.organization_id == organization_id,
        )
        if published_only:
            query = query.where(InternshipAssignment.status != AssignmentStatus.DRAFT)
        result = await self.db.execute(query.order_by(InternshipAssignment.created_at.desc()))
        return list(result.scalars().all())

    async def submission_counts(self, assignment_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        if not assignment_ids:
            return {}
        rows = await self.db.execute(
            select(
                AssignmentSubmission.assignment_id,
                func.count(),
                func.count(AssignmentSubmission.reviewed_at),
            )
            .where(AssignmentSubmission.assignment_id.in_(assignment_ids))
            .group_by(AssignmentSubmission.assignment_id)
        )
        return {a: (submitted, graded) for a, submitted, graded in rows.all()}

    async def create_assignment(
        self, internship: OurInternship, user_id: uuid.UUID, fields: dict
    ) -> InternshipAssignment:
        fields = self._normalise(fields)
        assignment = InternshipAssignment(
            organization_id=internship.organization_id,
            internship_id=internship.id,
            created_by_user_id=user_id,
            **fields,
        )
        self.db.add(assignment)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    async def update_assignment(self, assignment: InternshipAssignment, fields: dict) -> InternshipAssignment:
        if "rubric" in fields or "tasks" in fields or "starts_at" in fields or "deadline_at" in fields:
            merged = {
                "tasks": assignment.tasks,
                "rubric": assignment.rubric,
                "starts_at": assignment.starts_at,
                "deadline_at": assignment.deadline_at,
                "max_marks": assignment.max_marks,
                **fields,
            }
            normalised = self._normalise(merged)
            fields = {**fields, **{k: normalised[k] for k in ("tasks", "rubric", "max_marks")}}
        if "rubric" in fields and fields["rubric"] != assignment.rubric:
            await self._assert_nothing_graded(assignment)
        for key, value in fields.items():
            setattr(assignment, key, value)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment

    def _normalise(self, fields: dict) -> dict:
        fields = dict(fields)
        fields["tasks"] = _clean_tasks([dict(t) for t in fields.get("tasks") or []])
        rubric = _clean_rubric([dict(r) for r in fields.get("rubric") or []])
        fields["rubric"] = rubric
        if rubric:
            # With a rubric the marks come from it, so the total is always what the criteria add up to.
            fields["max_marks"] = sum(r["points"] for r in rubric)
        starts, deadline = fields.get("starts_at"), fields.get("deadline_at")
        if starts and deadline and deadline <= starts:
            raise ValidationError("The deadline must be after the start time.")
        return fields

    async def _assert_nothing_graded(self, assignment: InternshipAssignment) -> None:
        graded = (
            await self.db.execute(
                select(func.count()).where(
                    AssignmentSubmission.assignment_id == assignment.id,
                    AssignmentSubmission.reviewed_at.is_not(None),
                )
            )
        ).scalar_one()
        if graded:
            raise ConflictError("The rubric cannot be changed once submissions have been marked.")

    async def delete_assignment(self, assignment: InternshipAssignment) -> None:
        submissions = (
            await self.db.execute(
                select(AssignmentSubmission.id).where(AssignmentSubmission.assignment_id == assignment.id)
            )
        ).scalars().all()
        for submission_id in submissions:
            await self.files.delete_all(SUBMISSION_FILES, submission_id)
        await self.files.delete_all(ASSIGNMENT_FILES, assignment.id)
        await self.db.execute(delete(AssignmentSubmission).where(AssignmentSubmission.assignment_id == assignment.id))
        await self.db.delete(assignment)
        await self.db.flush()

    async def submission_rows(self, assignment: InternshipAssignment) -> list[dict]:
        enrolled = await self.enrolled(assignment.internship_id)
        submissions = {
            s.selection_id: s
            for s in (
                await self.db.execute(
                    select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == assignment.id)
                )
            )
            .scalars()
            .all()
        }
        files = await self.files.for_owners(SUBMISSION_FILES, [s.id for s in submissions.values()])
        rows = []
        for selection, person in enrolled:
            sub = submissions.get(selection.id)
            rows.append(
                {
                    "selection_id": selection.id,
                    "student_name": person.name,
                    "student_email": person.email,
                    "submitted": sub is not None,
                    "submitted_at": sub.submitted_at if sub else None,
                    "is_late": sub.is_late if sub else False,
                    "resubmission_count": sub.resubmission_count if sub else 0,
                    "note": sub.note if sub else None,
                    "files": [self.file_out(f) for f in files.get(sub.id, [])] if sub else [],
                    "rubric_scores": sub.rubric_scores if sub else None,
                    "score": float(sub.score) if sub and sub.score is not None else None,
                    "feedback": sub.feedback if sub else None,
                    "reviewed_at": sub.reviewed_at if sub else None,
                }
            )
        return rows

    def file_out(self, record) -> dict:
        return {
            "id": record.id,
            "filename": record.filename,
            "content_type": record.content_type,
            "size_bytes": record.size_bytes,
            "url": self.files.download_url(record),
            "created_at": record.created_at,
        }

    async def grade(
        self,
        assignment: InternshipAssignment,
        selection_id: uuid.UUID,
        payload: GradeRequest,
        user_id: uuid.UUID,
    ) -> AssignmentSubmission:
        submission = (
            await self.db.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == assignment.id,
                    AssignmentSubmission.selection_id == selection_id,
                )
            )
        ).scalar_one_or_none()
        if not submission:
            raise NotFoundError("Submission", selection_id)
        if assignment.rubric:
            given = payload.rubric_scores or {}
            rules = {r["id"]: r for r in assignment.rubric}
            unknown = set(given) - set(rules)
            if unknown:
                raise ValidationError("Some marks are for criteria that are not in the rubric.")
            for rule_id, marks in given.items():
                if marks < 0 or marks > rules[rule_id]["points"]:
                    raise ValidationError(f"{rules[rule_id]['criterion']}: marks must be between 0 and {rules[rule_id]['points']}.")
            submission.rubric_scores = {rule_id: given.get(rule_id, 0) for rule_id in rules}
            submission.score = round(sum(submission.rubric_scores.values()), 2)
        else:
            if payload.score is None:
                raise ValidationError("Please enter the marks.")
            if payload.score > assignment.max_marks:
                raise ValidationError(f"Marks cannot be more than {assignment.max_marks}.")
            submission.rubric_scores = None
            submission.score = round(payload.score, 2)
        submission.feedback = (payload.feedback or "").strip() or None
        submission.reviewed_at = _now()
        submission.reviewed_by_user_id = user_id
        await self.db.flush()
        return submission

    # ---------------- assignments: the student ----------------

    def can_submit(self, assignment: InternshipAssignment, submission: AssignmentSubmission | None) -> bool:
        now = _now()
        if assignment.status != AssignmentStatus.PUBLISHED:
            return False
        if assignment.starts_at and now < assignment.starts_at:
            return False
        if assignment.deadline_at and now > assignment.deadline_at and not assignment.allow_late:
            return False
        return not (submission and submission.reviewed_at)

    async def my_submission(self, assignment_id: uuid.UUID, selection_id: uuid.UUID) -> AssignmentSubmission | None:
        return (
            await self.db.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == assignment_id,
                    AssignmentSubmission.selection_id == selection_id,
                )
            )
        ).scalar_one_or_none()

    async def submit(
        self,
        assignment: InternshipAssignment,
        selection: InternshipSelection,
        user_id: uuid.UUID,
        note: str | None,
        uploads: list[tuple[str, str, bytes]],
    ) -> AssignmentSubmission:
        existing = await self.my_submission(assignment.id, selection.id)
        if assignment.status != AssignmentStatus.PUBLISHED:
            raise ValidationError("This assignment is not open for submissions.")
        now = _now()
        if assignment.starts_at and now < assignment.starts_at:
            raise ValidationError("This assignment has not opened yet.")
        late = bool(assignment.deadline_at and now > assignment.deadline_at)
        if late and not assignment.allow_late:
            raise ValidationError("The deadline for this assignment has passed.")
        if existing and existing.reviewed_at:
            raise ValidationError("This submission has already been marked, so it can no longer be changed.")
        kept = (await self.files.for_owners(SUBMISSION_FILES, [existing.id])).get(existing.id, []) if existing else []
        # New files replace the earlier ones; with none given the earlier files stay.
        total = len(uploads) if uploads else len(kept)
        if total == 0 and not (note or "").strip():
            raise ValidationError("Please attach a file or write a note.")
        if total > assignment.max_files:
            raise ValidationError(f"You can attach at most {assignment.max_files} files.")
        clean_note = (note or "").strip()[:8000] or None
        if existing:
            existing.note = clean_note
            existing.submitted_at = now
            existing.is_late = late
            existing.resubmission_count += 1
            submission = existing
        else:
            submission = AssignmentSubmission(
                organization_id=assignment.organization_id,
                assignment_id=assignment.id,
                selection_id=selection.id,
                note=clean_note,
                submitted_at=now,
                is_late=late,
            )
            self.db.add(submission)
        await self.db.flush()
        if uploads:
            stored = []
            for filename, content_type, data in uploads:
                stored.append(
                    await self.files.store(
                        organization_id=assignment.organization_id,
                        internship_id=assignment.internship_id,
                        owner_type=SUBMISSION_FILES,
                        owner_id=submission.id,
                        uploaded_by=user_id,
                        filename=filename,
                        content_type=content_type,
                        data=data,
                    )
                )
            for old in kept:
                await self.files.delete(old)
        return submission

    # ---------------- exams ----------------

    async def exams_of(self, internship_id: uuid.UUID, organization_id: uuid.UUID) -> list[WorkshopExam]:
        result = await self.db.execute(
            select(WorkshopExam)
            .where(WorkshopExam.internship_id == internship_id, WorkshopExam.organization_id == organization_id)
            .order_by(WorkshopExam.created_at.desc())
        )
        return list(result.scalars().all())

    async def exam_summaries(self, exams: list[WorkshopExam]) -> list[dict]:
        if not exams:
            return []
        ids = [e.id for e in exams]
        questions = dict(
            (
                await self.db.execute(
                    select(WorkshopExamQuestion.exam_id, func.count())
                    .where(WorkshopExamQuestion.exam_id.in_(ids))
                    .group_by(WorkshopExamQuestion.exam_id)
                )
            ).all()
        )
        attendees: dict[uuid.UUID, list[WorkshopExamAttendee]] = {}
        for a in (
            await self.db.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id.in_(ids)))
        ).scalars():
            attendees.setdefault(a.exam_id, []).append(a)
        out = []
        for exam in exams:
            people = [a for a in attendees.get(exam.id, []) if not a.certificate_only]
            done = [a for a in people if a.submitted_at is not None]
            percents = [a.score * 100 / a.total_marks for a in done if a.total_marks and a.score is not None]
            out.append(
                {
                    "id": exam.id,
                    "title": exam.title,
                    "status": exam.status.value,
                    "duration_minutes": exam.duration_minutes,
                    "question_count": questions.get(exam.id, 0),
                    "attendee_count": len(people),
                    "submitted_count": len(done),
                    "average_percent": round(sum(percents) / len(percents), 1) if percents else None,
                }
            )
        return out

    async def available_exams(self, organization_id: uuid.UUID) -> list[WorkshopExam]:
        """Exams that belong to nothing yet, so they can be linked here."""
        result = await self.db.execute(
            select(WorkshopExam)
            .where(
                WorkshopExam.organization_id == organization_id,
                WorkshopExam.internship_id.is_(None),
                WorkshopExam.event_id.is_(None),
                WorkshopExam.hackathon_id.is_(None),
                WorkshopExam.workshop_id.is_(None),
            )
            .order_by(WorkshopExam.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_exam(self, exam_id: uuid.UUID, organization_id: uuid.UUID) -> WorkshopExam:
        exam = (
            await self.db.execute(
                select(WorkshopExam).where(WorkshopExam.id == exam_id, WorkshopExam.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if not exam:
            raise NotFoundError("Exam", exam_id)
        return exam

    async def link_exam(self, internship: OurInternship, exam_id: uuid.UUID) -> WorkshopExam:
        exam = await self.get_exam(exam_id, internship.organization_id)
        if exam.internship_id == internship.id:
            return exam
        if exam.internship_id or exam.event_id or exam.hackathon_id or exam.workshop_id:
            raise ConflictError("This exam already belongs to something else.")
        exam.internship_id = internship.id
        await self.db.flush()
        return exam

    async def unlink_exam(self, internship: OurInternship, exam_id: uuid.UUID) -> None:
        exam = await self.get_exam(exam_id, internship.organization_id)
        if exam.internship_id != internship.id:
            raise NotFoundError("Exam", exam_id)
        exam.internship_id = None
        await self.db.flush()

    async def linked_exam(self, internship: OurInternship, exam_id: uuid.UUID) -> WorkshopExam:
        exam = await self.get_exam(exam_id, internship.organization_id)
        if exam.internship_id != internship.id:
            raise NotFoundError("Exam", exam_id)
        return exam

    async def assign_exam(self, exam: WorkshopExam, send_invites: bool) -> tuple[int, int, list[uuid.UUID]]:
        """Put every enrolled student on the exam (each gets their own link). Returns (added, already there, invite
        ids to email)."""
        present = {
            a.email: a
            for a in (
                await self.db.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == exam.id))
            ).scalars()
        }
        added = existing = 0
        invite_ids: list[uuid.UUID] = []
        now = _now()
        for _, person in await self.enrolled(exam.internship_id):
            email = person.email.strip().lower()
            attendee = present.get(email)
            if attendee is not None:
                existing += 1
            else:
                attendee = WorkshopExamAttendee(
                    exam_id=exam.id,
                    name=person.name,
                    email=email,
                    access_token=secrets.token_urlsafe(24),
                    added_manually=True,
                )
                self.db.add(attendee)
                present[email] = attendee
                added += 1
            if send_invites and attendee.invited_at is None and attendee.submitted_at is None:
                await self.db.flush()
                attendee.invited_at = now
                invite_ids.append(attendee.id)
        await self.db.flush()
        return added, existing, invite_ids

    async def exam_results(self, exam: WorkshopExam) -> list[dict]:
        by_email = {
            a.email: a
            for a in (
                await self.db.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == exam.id))
            ).scalars()
        }
        rows = []
        for selection, person in await self.enrolled(exam.internship_id):
            attendee = by_email.get(person.email.strip().lower())
            rows.append(self._result_row(selection.id, person, attendee))
        return rows

    @staticmethod
    def _result_row(selection_id: uuid.UUID, person: InstitutionStudent, attendee: WorkshopExamAttendee | None) -> dict:
        if attendee is None:
            state = "not_assigned"
        elif attendee.submitted_at is not None:
            state = "submitted"
        elif attendee.started_at is not None:
            state = "in_progress"
        else:
            state = "not_started"
        scored = attendee is not None and attendee.submitted_at is not None and attendee.total_marks
        return {
            "selection_id": selection_id,
            "student_name": person.name,
            "student_email": person.email,
            "state": state,
            "score": attendee.score if scored else None,
            "total_marks": attendee.total_marks if scored else None,
            "percent": round(attendee.score * 100 / attendee.total_marks, 1) if scored else None,
            "submitted_at": attendee.submitted_at if attendee else None,
        }

    async def my_exams(self, internship_id: uuid.UUID, organization_id: uuid.UUID, email: str) -> list[tuple]:
        """The internship's exams this student is on, as (exam, attendee) pairs; draft exams stay hidden."""
        email = email.strip().lower()
        rows = await self.db.execute(
            select(WorkshopExam, WorkshopExamAttendee)
            .join(WorkshopExamAttendee, WorkshopExamAttendee.exam_id == WorkshopExam.id)
            .where(
                WorkshopExam.internship_id == internship_id,
                WorkshopExam.organization_id == organization_id,
                WorkshopExam.status != WorkshopExamStatus.DRAFT,
                WorkshopExamAttendee.email == email,
                WorkshopExamAttendee.certificate_only.is_(False),
            )
            .order_by(WorkshopExam.created_at.desc())
        )
        return [(e, a) for e, a in rows.all()]
