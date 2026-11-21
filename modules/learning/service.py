"""The shared learning read models: what both Learning workspaces show. Nothing here is stored or copied: every row is read from the record
that owns it (an internship's assignments, exams and projects; the course's assessments, practicals and viva; the enrolments). Each
activity keeps its own grading rules; no combined score is invented."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from modules.authentication.models import User
from modules.courses.models import Course
from modules.courses.repository import CourseRepository
from modules.examinations.practicals.repository import PracticalRepository
from modules.examinations.practicals.models import PracticalExam
from modules.examinations.viva.models import VivaExam
from modules.examinations.viva.repository import VivaRepository
from modules.institutions.models import InstitutionStudent
from modules.internship_learning.project_models import InternshipProject, ProjectSubmission
from modules.internship_learning.project_service import ProjectService
from modules.internship_learning.service import InternshipLearningService
from modules.learning.schemas import (
    CourseRef,
    EnrollmentRow,
    EnrollmentsView,
    IndependentEnrollment,
    InternshipRef,
    LearningContext,
    ResultRow,
    ResultsView,
    TabDef,
)
from modules.learning.scope import authorize_internship, has_permission, visible_internship_ids
from modules.lms.assessments.models import Assessment
from modules.lms.assessments.service import AssessmentService
from modules.lms.enrollment.models import Enrollment
from modules.lms.progress.service import ProgressService
from modules.our_internships.access import InstructorService
from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship
from modules.our_internships.onboarding import STAGE_LABELS, OnboardingService, grant_blockers, stage_of
from modules.students.models import Student

# The tabs, in order. Both the internship's Learning tab and the course's Learning tab render exactly these.
TABS = [
    TabDef(key="curriculum", label="Curriculum"),
    TabDef(key="enrollments", label="Enrollments"),
    TabDef(key="evaluations", label="Evaluations"),
    TabDef(key="projects", label="Projects"),
    TabDef(key="discussions", label="Discussions"),
    TabDef(key="practicals", label="Practicals"),
    TabDef(key="viva", label="Viva"),
]
KINDS = ["exam", "assignment", "assessment", "project", "practical", "viva"]

COURSE_CAPS = {
    "curriculum_view": "courses.view",
    "curriculum_manage": "courses.manage",
    "enrollments_view": "lms.enrollment.view",
    "enrollments_manage": "lms.enrollment.manage",
    "assignments_view": "lms.assignments.view",
    "assignments_manage": "lms.assignments.manage",
    "assessments_view": "lms.assessments.view",
    "assessments_manage": "lms.assessments.manage",
    "exams_view": "examinations.exams.view",
    "exams_manage": "examinations.exams.manage",
    "practicals_view": "examinations.practicals.view",
    "practicals_manage": "examinations.practicals.manage",
    "viva_view": "examinations.viva.view",
    "viva_manage": "examinations.viva.manage",
    "discussions_participate": "lms.discussions.participate",
}


def _percent(score, total) -> float | None:
    return round(score * 100 / total, 1) if score is not None and total else None


class LearningService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ context

    async def _internship_refs(self, user: User, internships: list[OurInternship]) -> list[InternshipRef]:
        service = InstructorService(self.db)
        is_global_view = await service.has_global(user, "view")
        is_global_manage = await service.has_global(user, "manage")
        mine = await service.active_internship_ids(user)
        out = []
        for i in internships:
            reach = is_global_view or i.id in mine
            out.append(
                InternshipRef(
                    id=i.id, title=i.title, status=i.status.value, can_view=reach,
                    can_manage=is_global_manage or i.id in mine, can_delete=is_global_manage,
                )
            )
        return out

    async def context(self, user: User, organization_id: uuid.UUID, *, course_id: uuid.UUID | None, internship_id: uuid.UUID | None) -> LearningContext:
        internships: list[OurInternship] = []
        if internship_id is not None:
            internship = await authorize_internship(self.db, user, organization_id, internship_id, "view")
            internships = [internship]
            course_id = internship.lms_course_id
        elif course_id is not None:
            ids = await visible_internship_ids(self.db, user, organization_id, course_id, "view")
            if ids:
                internships = list((await self.db.execute(select(OurInternship).where(OurInternship.id.in_(list(ids))).order_by(OurInternship.title))).scalars().all())
        else:
            raise NotFoundError("Course", None)

        course = None
        if course_id is not None:
            row = await CourseRepository(self.db).get_by_id(course_id, organization_id)
            if row is None:
                raise NotFoundError("Course", course_id)
            course = CourseRef(id=row.id, title=row.title, course_type=row.course_type.value, is_published=row.is_published)
        caps = {name: await has_permission(self.db, user, code) for name, code in COURSE_CAPS.items()}
        if internship_id is None and not caps["curriculum_view"] and not internships:
            raise AuthorizationError("This action requires the following permission(s): courses.view")
        return LearningContext(
            tabs=TABS, course=course, internships=await self._internship_refs(user, internships),
            needs_selector=internship_id is None and len(internships) > 1, course_caps=caps,
        )

    # ------------------------------------------------------------------ enrollments

    async def enrollments(self, user: User, organization_id: uuid.UUID, internship_id: uuid.UUID) -> EnrollmentsView:
        internship = await authorize_internship(self.db, user, organization_id, internship_id, "view")
        rows = (
            await self.db.execute(
                select(InternshipSelection, InstitutionStudent)
                .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
                .where(InternshipSelection.internship_id == internship_id)
                .order_by(InstitutionStudent.name)
            )
        ).all()
        problem = await OnboardingService(self.db).course_problem(internship)
        progress = ProgressService(self.db)
        out: list[EnrollmentRow] = []
        for selection, person in rows:
            course_id = selection.lms_course_id or internship.lms_course_id
            enrollment = None
            pct = done = total = None
            if selection.lms_student_id and course_id:
                enrollment = (
                    await self.db.execute(select(Enrollment).where(Enrollment.student_id == selection.lms_student_id, Enrollment.course_id == course_id))
                ).scalar_one_or_none()
                if enrollment is not None:
                    p = await progress.get_course_progress(organization_id, selection.lms_student_id, course_id)
                    pct, done, total = p.percent_complete, p.completed_lessons, p.total_lessons
            provenance = None
            if enrollment is not None and selection.lms_status in (LmsStatus.GRANTED, LmsStatus.REVOKED):
                provenance = "independent" if selection.lms_enrolment_preexisting else "internship"
            out.append(
                EnrollmentRow(
                    selection_id=selection.id, student_id=person.id, lms_student_id=selection.lms_student_id, name=person.name, email=person.email,
                    stage_label=STAGE_LABELS.get(stage_of(selection), stage_of(selection)),
                    lms_status=selection.lms_status.value, lms_granted_at=selection.lms_granted_at,
                    has_account=selection.lms_user_id is not None,
                    enrollment_id=enrollment.id if enrollment else None,
                    enrollment_status=enrollment.status.value if enrollment else None,
                    enrolled_on=enrollment.enrolled_on if enrollment else None,
                    provenance=provenance,
                    grant_blockers=grant_blockers(internship, selection, problem) if selection.lms_status != LmsStatus.GRANTED else [],
                    progress_percent=pct, completed_lessons=done, total_lessons=total,
                )
            )
        independent = None
        course_id = internship.lms_course_id
        if course_id is not None and await has_permission(self.db, user, "lms.enrollment.view"):
            tied = set(
                (
                    await self.db.execute(
                        select(InternshipSelection.lms_student_id).where(
                            InternshipSelection.lms_course_id == course_id,
                            InternshipSelection.lms_student_id.is_not(None),
                            InternshipSelection.lms_status.in_([LmsStatus.GRANTED, LmsStatus.REVOKED]),
                        )
                    )
                ).scalars().all()
            )
            ind = (
                await self.db.execute(
                    select(Enrollment, Student.full_name).join(Student, Student.id == Enrollment.student_id).where(
                        Enrollment.course_id == course_id, Student.organization_id == organization_id
                    ).order_by(Student.full_name)
                )
            ).all()
            independent = [
                IndependentEnrollment(enrollment_id=e.id, student_id=e.student_id, name=name, status=e.status.value, enrolled_on=e.enrolled_on)
                for e, name in ind if e.student_id not in tied
            ]
        return EnrollmentsView(internship_id=internship_id, course_id=internship.lms_course_id, rows=out, independent=independent)

    # ------------------------------------------------------------------ results

    async def _roster(self, internship_id: uuid.UUID) -> dict[uuid.UUID, dict]:
        """LMS student id -> {selection, name, email, access} for the internship's granted and revoked students."""
        rows = (
            await self.db.execute(
                select(InternshipSelection, InstitutionStudent)
                .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
                .where(
                    InternshipSelection.internship_id == internship_id,
                    InternshipSelection.lms_student_id.is_not(None),
                    InternshipSelection.lms_status.in_([LmsStatus.GRANTED, LmsStatus.REVOKED]),
                )
            )
        ).all()
        return {s.lms_student_id: {"selection": s.id, "name": p.name, "email": p.email, "access": s.lms_status.value} for s, p in rows}

    async def results(
        self,
        user: User,
        organization_id: uuid.UUID,
        *,
        internship_id: uuid.UUID | None,
        course_id: uuid.UUID | None,
        kind: str | None = None,
        status: str | None = None,
        q: str | None = None,
        student: str | None = None,
        activity_id: uuid.UUID | None = None,
    ) -> ResultsView:
        if internship_id is not None:
            internship = await authorize_internship(self.db, user, organization_id, internship_id, "view")
            course_id = internship.lms_course_id
        elif course_id is not None:
            if await CourseRepository(self.db).get_by_id(course_id, organization_id) is None:
                raise NotFoundError("Course", course_id)
        else:
            raise NotFoundError("Course", None)
        rows: list[ResultRow] = []
        included: list[str] = []

        async def can(code: str) -> bool:
            return await has_permission(self.db, user, code)

        roster = await self._roster(internship_id) if internship_id is not None else {}

        # ---- internship-owned: exams, assignments, projects (the internship's own records, read as they are)
        if internship_id is not None:
            learning = InternshipLearningService(self.db)
            included += ["exam", "assignment", "project"]
            for exam in await learning.exams_of(internship_id, organization_id):
                for r in await learning.exam_results(exam):
                    state = {"not_assigned": "not_started"}.get(r["state"], r["state"])
                    rows.append(ResultRow(
                        kind="exam", scope="internship", activity_id=exam.id, activity_title=exam.title, internship_id=internship_id,
                        student_key=str(r["selection_id"]), student_name=r["student_name"], student_email=r["student_email"],
                        access_status=r["access_status"], state=state, completed=state == "submitted",
                        score=r["score"], total_marks=r["total_marks"], percent=r["percent"], at=r["submitted_at"],
                    ))
            for a in await learning.list_assignments(internship_id, organization_id):
                for r in await learning.submission_rows(a):
                    state = "graded" if r["reviewed_at"] else "submitted" if r["submitted"] else "not_started"
                    rows.append(ResultRow(
                        kind="assignment", scope="internship", activity_id=a.id, activity_title=a.title, internship_id=internship_id,
                        student_key=str(r["selection_id"]), student_name=r["student_name"], student_email=r["student_email"],
                        access_status=r["access_status"], state=state, completed=state != "not_started",
                        score=r["score"] if r["reviewed_at"] else None, total_marks=float(a.max_marks),
                        percent=_percent(r["score"], a.max_marks) if r["reviewed_at"] else None, at=r["submitted_at"],
                    ))
            projects = {p.id: p for p in await ProjectService(self.db).list_all(internship_id, organization_id)}
            if projects:
                subs = {
                    (s.project_id, s.selection_id): s
                    for s in (await self.db.execute(select(ProjectSubmission).where(ProjectSubmission.project_id.in_(list(projects))))).scalars()
                }
                for r in await ProjectService(self.db).selection_rows(internship_id):
                    if r["project_id"] is None:
                        continue
                    project: InternshipProject = projects[r["project_id"]]
                    sub = subs.get((project.id, r["selection_id"]))
                    graded = sub is not None and sub.final_marks is not None
                    state = "graded" if graded else "submitted" if r["submitted"] else "in_progress"
                    rows.append(ResultRow(
                        kind="project", scope="internship", activity_id=project.id, activity_title=project.title, internship_id=internship_id,
                        student_key=str(r["selection_id"]), student_name=r["student_name"], student_email=r["student_email"],
                        access_status=r["access_status"], state=state, completed=state != "in_progress",
                        score=float(sub.final_marks) if graded else None, total_marks=float(project.max_marks),
                        percent=_percent(float(sub.final_marks), project.max_marks) if graded else None, at=r["submitted_at"],
                    ))

        # ---- course-native: assessments, practicals, viva (a cohort's own are always its; course-wide ones need the course permission)
        if course_id is not None:
            service = AssessmentService(self.db)
            # assessments
            course_wide_ok = await can("lms.assessments.view")
            if internship_id is not None or course_wide_ok:
                included.append("assessment")
                wanted = (
                    await self.db.execute(select(Assessment).where(Assessment.course_id == course_id).order_by(Assessment.created_at))
                ).scalars().all()
                for a in wanted:
                    if a.internship_id is None and not course_wide_ok:
                        continue
                    if a.internship_id is not None and a.internship_id != internship_id:
                        continue
                    attempts = {r["student_id"]: r for r in await service.list_attempts(a.id, course_id, organization_id, internship_id=internship_id)}
                    for sid, info in (roster.items() if internship_id is not None else [(k, None) for k in attempts]):
                        r = attempts.get(sid)
                        done = r is not None and r["status"].value != "in_progress"
                        state = "graded" if done else "in_progress" if r else "not_started"
                        name = info["name"] if info else (r["student_name"] or "Student")
                        total = r["total_marks"] if r and r["total_marks"] is not None else a.total_marks
                        rows.append(ResultRow(
                            kind="assessment", scope="internship" if a.internship_id else "course", activity_id=a.id, activity_title=a.title,
                            internship_id=internship_id if internship_id else None,
                            student_key=str(info["selection"]) if info else str(sid), lms_student_id=sid, student_name=name, student_email=info["email"] if info else None,
                            access_status=info["access"] if info else None, state=state, completed=done,
                            score=float(r["score"]) if done and r["score"] is not None else None, total_marks=float(total),
                            percent=_percent(r["score"], total) if done and r["score"] is not None else None,
                            passed=(r["score"] * 100 / total >= a.passing_marks * 100 / a.total_marks) if done and r["score"] is not None and total else None,
                            at=r["submitted_at"] if r else None,
                        ))
            for label, model, repo_cls, ok in (
                ("practical", PracticalExam, PracticalRepository, await can("examinations.practicals.view")),
                ("viva", VivaExam, VivaRepository, await can("examinations.viva.view")),
            ):
                if internship_id is None and not ok:
                    continue
                included.append(label)
                repo = repo_cls(self.db)
                activities = (await self.db.execute(select(model).where(model.course_id == course_id).order_by(model.exam_date))).scalars().all()
                for act in activities:
                    if act.internship_id is None and not ok:
                        continue
                    if act.internship_id is not None and act.internship_id != internship_id:
                        continue
                    results = {r.student_id: r for r in await repo.list_results(act.id)}
                    people = roster.items() if internship_id is not None else [(sid, None) for sid in results]
                    names = {}
                    if internship_id is None:
                        for sid in results:
                            st = (await self.db.execute(select(Student.full_name).where(Student.id == sid, Student.organization_id == organization_id))).scalar_one_or_none()
                            names[sid] = st or "Student"
                    for sid, info in people:
                        r = results.get(sid)
                        rows.append(ResultRow(
                            kind=label, scope="internship" if act.internship_id else "course", activity_id=act.id, activity_title=act.title,
                            internship_id=internship_id if internship_id else None,
                            student_key=str(info["selection"]) if info else str(sid), lms_student_id=sid, student_name=info["name"] if info else names[sid],
                            student_email=info["email"] if info else None, access_status=info["access"] if info else None,
                            state="graded" if r else "not_started", completed=r is not None,
                            score=float(r.score) if r else None, total_marks=float(act.total_marks),
                            percent=_percent(r.score, act.total_marks) if r else None,
                            passed=(r.score >= act.passing_marks) if r else None, at=r.evaluated_at if r else None,
                        ))

        # ---- filters
        out = rows
        if kind:
            out = [r for r in out if r.kind == kind]
        if status == "completed":
            out = [r for r in out if r.completed]
        elif status == "pending":
            out = [r for r in out if not r.completed]
        if q:
            needle = q.strip().lower()
            out = [r for r in out if needle in r.student_name.lower() or needle in (r.student_email or "").lower() or needle in r.activity_title.lower()]
        if student:
            out = [r for r in out if r.student_key == student]
        if activity_id:
            out = [r for r in out if r.activity_id == activity_id]
        return ResultsView(internship_id=internship_id, course_id=course_id, rows=out, included=sorted(set(included), key=KINDS.index))
