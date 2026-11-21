import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.courses.repository import CourseRepository
from modules.examinations.practicals.service import PracticalService
from modules.examinations.viva.service import VivaService
from modules.internship_learning.service import InternshipLearningService
from modules.learning.scope import student_internship_ids, student_selection
from modules.lms.assessments.models import AssessmentQuestion
from modules.lms.assessments.service import AssessmentService
from modules.lms.enrollment.models import EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.lms.progress.service import ProgressService
from modules.our_internships.models import OurInternship
from modules.students.models import Student


class MyInternshipRef(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    open_assignments: int
    open_exams: int


class MyAssessment(BaseModel):
    id: uuid.UUID
    title: str
    assessment_type: str
    duration_minutes: int | None
    total_marks: int
    internship_id: uuid.UUID | None
    has_questions: bool
    state: str  # not_started | in_progress | submitted
    score: int | None = None
    result_total: int | None = None
    passed: bool | None = None


class MyEvaluation(BaseModel):
    id: uuid.UUID
    title: str
    exam_date: date
    internship_id: uuid.UUID | None
    total_marks: int
    passing_marks: int
    detail: str | None  # the rubric (practical) or the panel (viva)
    score: int | None
    remarks: str | None
    passed: bool | None


class MyProgress(BaseModel):
    percent_complete: float
    completed_lessons: int
    total_lessons: int


class MyCourseLearning(BaseModel):
    course_id: uuid.UUID
    course_title: str
    enrollment_status: str
    progress: MyProgress
    # the internships (the student's own, with granted access) that give them this course: their activities live under My Internship
    internships: list[MyInternshipRef]
    assessments: list[MyAssessment]
    practicals: list[MyEvaluation]
    viva: list[MyEvaluation]


class MyLearningService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def course(self, student: Student, course_id: uuid.UUID) -> MyCourseLearning | None:
        course = await CourseRepository(self.db).get_by_id(course_id, student.organization_id)
        enrollment = await EnrollmentRepository(self.db).get_by_student_and_course(student.id, course_id)
        if course is None or enrollment is None or enrollment.status == EnrollmentStatus.DROPPED:
            return None  # not enrolled, or access withdrawn: nothing, however the page was reached
        progress = await ProgressService(self.db).get_course_progress(student.organization_id, student.id, course_id)
        internship_ids = await student_internship_ids(self.db, student, course_id)

        learning = InternshipLearningService(self.db)
        refs: list[MyInternshipRef] = []
        if internship_ids:
            for internship in (await self.db.execute(select(OurInternship).where(OurInternship.id.in_(list(internship_ids))).order_by(OurInternship.title))).scalars():
                selection = await student_selection(self.db, student, internship.id)
                if selection is None:
                    continue
                open_a = 0
                for a in await learning.list_assignments(internship.id, student.organization_id, published_only=True):
                    if learning.can_submit(a, await learning.my_submission(a.id, selection.id)):
                        open_a += 1
                exams = await learning.my_exams(internship.id, student.organization_id, student.email or "", selection.id)
                refs.append(MyInternshipRef(
                    id=internship.id, title=internship.title, status=internship.status.value, open_assignments=open_a,
                    open_exams=sum(1 for e, att in exams if att.submitted_at is None and e.status.value == "open"),
                ))

        assessments = []
        service = AssessmentService(self.db)
        for a in await service.list_for_student(course_id, student, internship_ids):
            count = (await self.db.execute(select(func.count()).select_from(AssessmentQuestion).where(AssessmentQuestion.assessment_id == a.id))).scalar_one()
            result = await service.my_result(a, student)
            state = "not_started"
            if result is not None:
                state = "in_progress" if result["status"].value == "in_progress" else "submitted"
            assessments.append(MyAssessment(
                id=a.id, title=a.title, assessment_type=a.assessment_type.value, duration_minutes=a.duration_minutes, total_marks=a.total_marks,
                internship_id=a.internship_id, has_questions=count > 0, state=state,
                score=result["score"] if result else None, result_total=result["total_marks"] if result else None, passed=result["passed"] if result else None,
            ))

        def evaluations(rows: list[dict], detail_key: str) -> list[MyEvaluation]:
            return [
                MyEvaluation(
                    id=r["id"], title=r["title"], exam_date=r["exam_date"], internship_id=r["internship_id"], total_marks=r["total_marks"],
                    passing_marks=r["passing_marks"], detail=r.get(detail_key), score=r["score"], remarks=r["remarks"], passed=r["passed"],
                )
                for r in rows
            ]

        return MyCourseLearning(
            course_id=course_id, course_title=course.title, enrollment_status=enrollment.status.value,
            progress=MyProgress(percent_complete=progress.percent_complete, completed_lessons=progress.completed_lessons, total_lessons=progress.total_lessons),
            internships=refs, assessments=assessments,
            practicals=evaluations(await PracticalService(self.db).my_practicals(course_id, student), "rubric"),
            viva=evaluations(await VivaService(self.db).my_vivas(course_id, student), "panel_members"),
        )
