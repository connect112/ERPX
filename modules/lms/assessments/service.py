import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.courses.repository import CourseRepository
from modules.lms.assessments.models import Assessment, AssessmentAttempt, AssessmentQuestion, AttemptStatus
from modules.lms.assessments.repository import AssessmentRepository, AttemptRepository
from modules.lms.enrollment.access import require_live_enrollment
from modules.students.repository import StudentRepository

logger = get_logger(__name__)

_SUBMIT_GRACE = timedelta(seconds=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AssessmentService:
    """Assessments (quizzes, mock tests, coding tests) of a course. A course-wide assessment has no ``internship_id``; one that belongs to a
    single internship carries it and is reached only through that internship (see modules/learning/scope.py).

    An assessment with questions is a real, server-scored multiple-choice test: the correct options never leave the server while answering,
    the clock is the server's, and the score is worked out here from the saved answers. A student never supplies a score. An assessment
    with no questions keeps working as before: a container for scores that authorized staff record by hand."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AssessmentRepository(db)
        self.attempt_repo = AttemptRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_repo = StudentRepository(db)

    # ------------------------------------------------------------------ the assessment

    async def create_assessment(
        self, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Assessment:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        assessment = await self.repo.create(course_id=course_id, **fields)
        logger.info("assessment_created", assessment_id=str(assessment.id))
        return assessment

    async def _get_owned_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Assessment:
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        assessment = await self.repo.get_by_id(assessment_id)
        if not assessment or assessment.course_id != course_id:
            raise NotFoundError("Assessment", assessment_id)
        return assessment

    async def list_assessments(
        self,
        course_id: uuid.UUID,
        organization_id: uuid.UUID,
        *,
        internship_id: uuid.UUID | None = None,
        include_course: bool = False,
    ) -> list[Assessment]:
        """Course-wide assessments (no internship given), or one internship's own (plus the course-wide ones when asked)."""
        course = await self.course_repo.get_by_id(course_id, organization_id)
        if not course:
            raise NotFoundError("Course", course_id)
        clause = Assessment.internship_id.is_(None)
        if internship_id is not None:
            clause = Assessment.internship_id == internship_id
            if include_course:
                clause = or_(clause, Assessment.internship_id.is_(None))
        rows = await self.db.execute(select(Assessment).where(Assessment.course_id == course_id, clause).order_by(Assessment.created_at))
        return list(rows.scalars().all())

    async def list_for_student(self, course_id: uuid.UUID, student, internship_ids: set[uuid.UUID]) -> list[Assessment]:
        """Published assessments a student may see: the course-wide ones, and those of internships they hold granted access on."""
        clause = Assessment.internship_id.is_(None)
        if internship_ids:
            clause = or_(clause, Assessment.internship_id.in_(list(internship_ids)))
        rows = await self.db.execute(
            select(Assessment).where(Assessment.course_id == course_id, Assessment.is_published.is_(True), clause).order_by(Assessment.created_at)
        )
        return list(rows.scalars().all())

    async def get_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Assessment:
        return await self._get_owned_assessment(assessment_id, course_id, organization_id)

    async def update_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Assessment:
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        updated = await self.repo.update(assessment, **fields)
        logger.info("assessment_updated", assessment_id=str(assessment_id))
        return updated

    async def delete_assessment(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        attempted = (await self.db.execute(select(func.count()).select_from(AssessmentAttempt).where(AssessmentAttempt.assessment_id == assessment_id))).scalar_one()
        if attempted:
            raise ConflictError("Students have already attempted this assessment, so it cannot be deleted. Unpublish it instead.")
        await self.repo.delete(assessment)
        logger.info("assessment_deleted", assessment_id=str(assessment_id))

    # ------------------------------------------------------------------ questions (staff)

    async def questions(self, assessment_id: uuid.UUID) -> list[AssessmentQuestion]:
        rows = await self.db.execute(
            select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment_id).order_by(AssessmentQuestion.order_index, AssessmentQuestion.created_at)
        )
        return list(rows.scalars().all())

    async def _assert_nobody_started(self, assessment_id: uuid.UUID) -> None:
        started = (await self.db.execute(select(func.count()).select_from(AssessmentAttempt).where(AssessmentAttempt.assessment_id == assessment_id))).scalar_one()
        if started:
            raise ConflictError("Students have already started this assessment, so its questions can no longer be changed.")

    async def add_question(self, assessment: Assessment, **fields) -> AssessmentQuestion:
        await self._assert_nobody_started(assessment.id)
        order = (await self.db.execute(select(func.coalesce(func.max(AssessmentQuestion.order_index), 0)).where(AssessmentQuestion.assessment_id == assessment.id))).scalar_one()
        question = AssessmentQuestion(assessment_id=assessment.id, order_index=order + 1, **fields)
        self.db.add(question)
        await self.db.flush()
        return question

    async def _question(self, assessment: Assessment, question_id: uuid.UUID) -> AssessmentQuestion:
        question = (
            await self.db.execute(select(AssessmentQuestion).where(AssessmentQuestion.id == question_id, AssessmentQuestion.assessment_id == assessment.id))
        ).scalar_one_or_none()
        if question is None:
            raise NotFoundError("Question", question_id)
        return question

    async def update_question(self, assessment: Assessment, question_id: uuid.UUID, **fields) -> AssessmentQuestion:
        await self._assert_nobody_started(assessment.id)
        question = await self._question(assessment, question_id)
        for key, value in fields.items():
            setattr(question, key, value)
        await self.db.flush()
        return question

    async def delete_question(self, assessment: Assessment, question_id: uuid.UUID) -> None:
        await self._assert_nobody_started(assessment.id)
        await self.db.delete(await self._question(assessment, question_id))
        await self.db.flush()

    # ------------------------------------------------------------------ taking an assessment (student, as themselves)

    @staticmethod
    def _deadline(attempt: AssessmentAttempt, assessment: Assessment) -> datetime | None:
        if not assessment.duration_minutes:
            return None
        return attempt.started_at + timedelta(minutes=assessment.duration_minutes)

    def _remaining(self, attempt: AssessmentAttempt, assessment: Assessment) -> int | None:
        deadline = self._deadline(attempt, assessment)
        return None if deadline is None else max(0, int((deadline - _now()).total_seconds()))

    @staticmethod
    def score_answers(questions: list[AssessmentQuestion], answers: dict) -> tuple[int, int]:
        """(score, total) from the saved answers: a question earns its marks only when exactly the correct options were chosen."""
        score = total = 0
        for q in questions:
            total += q.marks
            chosen = sorted({int(i) for i in answers.get(str(q.id), []) if isinstance(i, int)})
            if chosen and chosen == sorted(int(i) for i in q.correct_indices):
                score += q.marks
        return score, total

    async def _finalize(self, attempt: AssessmentAttempt, questions: list[AssessmentQuestion]) -> None:
        attempt.score, attempt.total_marks = self.score_answers(questions, attempt.answers or {})
        attempt.submitted_at = _now()
        attempt.status = AttemptStatus.EVALUATED
        await self.db.flush()

    async def _own_attempt(self, assessment: Assessment, student) -> AssessmentAttempt | None:
        return await self.attempt_repo.get_by_assessment_and_student(assessment.id, student.id)

    async def _expire_if_due(self, attempt: AssessmentAttempt, assessment: Assessment, questions: list[AssessmentQuestion]) -> None:
        if attempt.status == AttemptStatus.IN_PROGRESS and questions:
            remaining = self._remaining(attempt, assessment)
            if remaining is not None and remaining <= 0:
                await self._finalize(attempt, questions)

    async def take_start(self, assessment: Assessment, student) -> dict:
        """Begin, or resume, the student's single attempt and return the questions without their answers."""
        await require_live_enrollment(self.db, student, assessment.course_id)
        if not assessment.is_published:
            raise ValidationError("This assessment is not yet published.")
        questions = await self.questions(assessment.id)
        if not questions:
            raise ValidationError("This assessment has no questions to take; your result is recorded by your instructor.")
        attempt = await self._own_attempt(assessment, student)
        if attempt is None:
            attempt = await self.attempt_repo.create(assessment_id=assessment.id, student_id=student.id, started_at=_now())
        await self._expire_if_due(attempt, assessment, questions)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ConflictError("You have already submitted this assessment.")
        # the same order and option order on every reload for one attempt, different between students
        order = random.Random(str(attempt.id))
        shuffled = list(questions)
        order.shuffle(shuffled)
        payload = []
        for q in shuffled:
            options = list(enumerate(q.options))
            random.Random(f"{attempt.id}:{q.id}").shuffle(options)
            payload.append({"id": q.id, "text": q.text, "marks": q.marks, "allow_multiple": q.allow_multiple, "options": [{"index": i, "text": t} for i, t in options]})
        return {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "remaining_seconds": self._remaining(attempt, assessment),
            "questions": payload,
            "saved_answers": {k: list(v) for k, v in (attempt.answers or {}).items()},
        }

    async def take_save(self, assessment: Assessment, student, answers: dict[str, list[int]]) -> None:
        attempt = await self._own_attempt(assessment, student)
        if attempt is None or attempt.status != AttemptStatus.IN_PROGRESS:
            return
        await require_live_enrollment(self.db, student, assessment.course_id)
        questions = await self.questions(assessment.id)
        remaining = self._remaining(attempt, assessment)
        if remaining is not None and remaining <= 0 and _now() - self._deadline(attempt, assessment) > _SUBMIT_GRACE:
            return
        by_id = {str(q.id): q for q in questions}
        merged = dict(attempt.answers or {})
        for key, picked in answers.items():
            question = by_id.get(key)
            if question is None:
                continue
            clean = sorted({i for i in picked if isinstance(i, int) and 0 <= i < len(question.options)})
            if not question.allow_multiple:
                clean = clean[:1]
            merged[key] = clean
        attempt.answers = merged
        await self.db.flush()

    async def take_submit(self, assessment: Assessment, student, answers: dict[str, list[int]]) -> AssessmentAttempt:
        attempt = await self._own_attempt(assessment, student)
        if attempt is None:
            raise ValidationError("You haven't started this assessment yet.")
        if attempt.status == AttemptStatus.IN_PROGRESS:
            await self.take_save(assessment, student, answers)
            await self._finalize(attempt, await self.questions(assessment.id))
        return attempt

    async def my_result(self, assessment: Assessment, student) -> dict | None:
        attempt = await self._own_attempt(assessment, student)
        if attempt is None:
            return None
        questions = await self.questions(assessment.id)
        await self._expire_if_due(attempt, assessment, questions)
        done = attempt.status != AttemptStatus.IN_PROGRESS
        show = done and (assessment.show_result or attempt.total_marks is None)
        # an attempt staff recorded by hand has no total of its own: it is out of the assessment's marks
        total = attempt.total_marks if attempt.total_marks is not None else assessment.total_marks
        passed = None
        if show and attempt.score is not None and total:
            passed = attempt.score * 100 / total >= assessment.passing_marks * 100 / assessment.total_marks
        return {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "submitted_at": attempt.submitted_at,
            "score": attempt.score if show else None,
            "total_marks": total if show else None,
            "passed": passed,
        }

    # ------------------------------------------------------------------ recording by staff (legacy and manual assessments)

    async def start_attempt(self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, student) -> AssessmentAttempt:
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        if not assessment.is_published:
            raise ValidationError("This assessment is not yet published.")
        await require_live_enrollment(self.db, student, course_id)
        existing = await self.attempt_repo.get_by_assessment_and_student(assessment_id, student.id)
        if existing:
            raise ConflictError("This student has already attempted this assessment.")
        attempt = await self.attempt_repo.create(assessment_id=assessment_id, student_id=student.id, started_at=_now())
        logger.info("assessment_attempt_started", attempt_id=str(attempt.id))
        return attempt

    async def submit_attempt(
        self, attempt_id: uuid.UUID, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, score: int
    ) -> AssessmentAttempt:
        """Staff-authorized score for an attempt of an assessment that has no questions."""
        assessment = await self._get_owned_assessment(assessment_id, course_id, organization_id)
        attempt = await self.attempt_repo.get_by_id(attempt_id)
        if not attempt or attempt.assessment_id != assessment_id:
            raise NotFoundError("Attempt", attempt_id)
        if await self.questions(assessment_id):
            raise ValidationError("This assessment is scored from the student's answers; a score cannot be entered by hand.")
        if score > assessment.total_marks:
            raise ValidationError(f"Score cannot exceed the total marks of {assessment.total_marks}.")
        submitted = await self.attempt_repo.submit(attempt, score)
        logger.info("assessment_attempt_submitted", attempt_id=str(attempt_id), score=score)
        return submitted

    async def list_attempts(
        self, assessment_id: uuid.UUID, course_id: uuid.UUID, organization_id: uuid.UUID, *, internship_id: uuid.UUID | None = None
    ) -> list[dict]:
        """Attempts with the student's name. With an internship, only that internship's students (revoked ones kept, marked)."""
        await self._get_owned_assessment(assessment_id, course_id, organization_id)
        attempts = await self.attempt_repo.list_for_assessment(assessment_id)
        access: dict[uuid.UUID, str] = {}
        if internship_id is not None:
            from modules.our_internships.models import InternshipSelection, LmsStatus

            rows = await self.db.execute(
                select(InternshipSelection.lms_student_id, InternshipSelection.lms_status).where(
                    InternshipSelection.internship_id == internship_id,
                    InternshipSelection.lms_student_id.is_not(None),
                    InternshipSelection.lms_status.in_([LmsStatus.GRANTED, LmsStatus.REVOKED]),
                )
            )
            access = {sid: st.value for sid, st in rows.all()}
            attempts = [a for a in attempts if a.student_id in access]
        out = []
        for a in attempts:
            student = await self.student_repo.get_by_id(a.student_id, organization_id)
            row = {
                "id": a.id, "assessment_id": a.assessment_id, "student_id": a.student_id, "started_at": a.started_at,
                "submitted_at": a.submitted_at, "score": a.score, "total_marks": a.total_marks, "status": a.status,
                "access_status": access.get(a.student_id), "student_name": student.full_name if student else None,
            }
            out.append(row)
        return out
