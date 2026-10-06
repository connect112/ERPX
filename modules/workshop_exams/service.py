import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.workshop_exams.models import (
    WorkshopExam,
    WorkshopExamAttendee,
    WorkshopExamQuestion,
    WorkshopExamStatus,
)

logger = get_logger(__name__)

# A submit that lands a few seconds after the timer hit zero (slow wifi,
# a request already in flight) is still accepted rather than discarded.
_SUBMIT_GRACE = timedelta(seconds=20)

# Ceiling on registrations through the open link: a basic guard against
# someone scripting thousands of fake sign-ups.
_MAX_ATTENDEES = 3000


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WorkshopExamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- admin: exams ----------------

    async def create_exam(self, organization_id: uuid.UUID, **fields) -> WorkshopExam:
        exam = WorkshopExam(organization_id=organization_id, public_code=secrets.token_urlsafe(9), **fields)
        self.db.add(exam)
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    async def get_exam(self, exam_id: uuid.UUID, organization_id: uuid.UUID) -> WorkshopExam:
        result = await self.db.execute(
            select(WorkshopExam).where(
                WorkshopExam.id == exam_id, WorkshopExam.organization_id == organization_id
            )
        )
        exam = result.scalar_one_or_none()
        if not exam:
            raise NotFoundError("Workshop exam", exam_id)
        return exam

    async def list_exams(self, organization_id: uuid.UUID) -> list[tuple[WorkshopExam, int, int]]:
        result = await self.db.execute(
            select(WorkshopExam)
            .where(WorkshopExam.organization_id == organization_id)
            .order_by(WorkshopExam.created_at.desc())
        )
        exams = list(result.scalars().all())
        if not exams:
            return []
        ids = [e.id for e in exams]
        q_counts = dict(
            (
                await self.db.execute(
                    select(WorkshopExamQuestion.exam_id, func.count())
                    .where(WorkshopExamQuestion.exam_id.in_(ids))
                    .group_by(WorkshopExamQuestion.exam_id)
                )
            ).all()
        )
        a_counts = dict(
            (
                await self.db.execute(
                    select(WorkshopExamAttendee.exam_id, func.count())
                    .where(WorkshopExamAttendee.exam_id.in_(ids))
                    .group_by(WorkshopExamAttendee.exam_id)
                )
            ).all()
        )
        return [(e, q_counts.get(e.id, 0), a_counts.get(e.id, 0)) for e in exams]

    async def counts_for(self, exam_id: uuid.UUID) -> tuple[int, int]:
        q = (
            await self.db.execute(
                select(func.count()).select_from(WorkshopExamQuestion).where(WorkshopExamQuestion.exam_id == exam_id)
            )
        ).scalar_one()
        a = (
            await self.db.execute(
                select(func.count()).select_from(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == exam_id)
            )
        ).scalar_one()
        return q, a

    async def update_exam(self, exam: WorkshopExam, fields: dict) -> WorkshopExam:
        # Unlike a plain PATCH, certificate_release_at may legitimately be
        # set to None (to unschedule), so the caller passes only the keys
        # the client actually sent.
        for key, value in fields.items():
            setattr(exam, key, value)
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    async def delete_exam(self, exam: WorkshopExam) -> None:
        await self.db.delete(exam)
        await self.db.flush()

    async def set_status(self, exam: WorkshopExam, status: WorkshopExamStatus) -> WorkshopExam:
        if status == WorkshopExamStatus.OPEN:
            question_count, _ = await self.counts_for(exam.id)
            if question_count == 0:
                raise ValidationError("Add at least one question before opening the exam.")
        exam.status = status
        await self.db.flush()
        await self.db.refresh(exam)
        return exam

    # ---------------- admin: questions ----------------

    async def _assert_nobody_started(self, exam: WorkshopExam) -> None:
        # Changing the paper under someone who is already answering it
        # would change what their score means.
        started = (
            await self.db.execute(
                select(WorkshopExamAttendee.id)
                .where(WorkshopExamAttendee.exam_id == exam.id, WorkshopExamAttendee.started_at.is_not(None))
                .limit(1)
            )
        ).first()
        if started:
            raise ValidationError("Questions can't be changed once anyone has started the exam.")

    async def add_questions(self, exam: WorkshopExam, items: list[dict]) -> list[WorkshopExamQuestion]:
        await self._assert_nobody_started(exam)
        next_index = (
            await self.db.execute(
                select(func.coalesce(func.max(WorkshopExamQuestion.order_index), -1)).where(
                    WorkshopExamQuestion.exam_id == exam.id
                )
            )
        ).scalar_one() + 1
        created = []
        for offset, item in enumerate(items):
            question = WorkshopExamQuestion(exam_id=exam.id, order_index=next_index + offset, **item)
            self.db.add(question)
            created.append(question)
        await self.db.flush()
        return created

    async def update_question(
        self, exam: WorkshopExam, question_id: uuid.UUID, fields: dict
    ) -> WorkshopExamQuestion:
        await self._assert_nobody_started(exam)
        result = await self.db.execute(
            select(WorkshopExamQuestion).where(
                WorkshopExamQuestion.id == question_id, WorkshopExamQuestion.exam_id == exam.id
            )
        )
        question = result.scalar_one_or_none()
        if not question:
            raise NotFoundError("Question", question_id)
        for key, value in fields.items():
            setattr(question, key, value)
        await self.db.flush()
        await self.db.refresh(question)
        return question

    async def list_questions(self, exam_id: uuid.UUID) -> list[WorkshopExamQuestion]:
        result = await self.db.execute(
            select(WorkshopExamQuestion)
            .where(WorkshopExamQuestion.exam_id == exam_id)
            .order_by(WorkshopExamQuestion.order_index)
        )
        return list(result.scalars().all())

    async def delete_question(self, exam: WorkshopExam, question_id: uuid.UUID) -> None:
        await self._assert_nobody_started(exam)
        result = await self.db.execute(
            select(WorkshopExamQuestion).where(
                WorkshopExamQuestion.id == question_id, WorkshopExamQuestion.exam_id == exam.id
            )
        )
        question = result.scalar_one_or_none()
        if not question:
            raise NotFoundError("Question", question_id)
        await self.db.delete(question)
        await self.db.flush()

    # ---------------- admin: attendees ----------------

    async def import_attendees(self, exam: WorkshopExam, rows: list[tuple[str, str]]) -> tuple[int, int]:
        existing = {
            e
            for (e,) in (
                await self.db.execute(
                    select(WorkshopExamAttendee.email).where(WorkshopExamAttendee.exam_id == exam.id)
                )
            ).all()
        }
        added = skipped = 0
        for name, email in rows:
            email = email.strip().lower()
            if email in existing:
                skipped += 1
                continue
            existing.add(email)
            self.db.add(
                WorkshopExamAttendee(
                    exam_id=exam.id,
                    name=name.strip(),
                    email=email,
                    access_token=secrets.token_urlsafe(24),
                )
            )
            added += 1
        await self.db.flush()
        return added, skipped

    async def list_attendees(self, exam_id: uuid.UUID) -> list[WorkshopExamAttendee]:
        result = await self.db.execute(
            select(WorkshopExamAttendee)
            .where(WorkshopExamAttendee.exam_id == exam_id)
            .order_by(WorkshopExamAttendee.name)
        )
        return list(result.scalars().all())

    async def mark_invites(self, exam: WorkshopExam, resend_all: bool) -> list[uuid.UUID]:
        attendees = await self.list_attendees(exam.id)
        now = _now()
        ids = []
        for attendee in attendees:
            if attendee.submitted_at is not None:
                continue
            if attendee.invited_at is not None and not resend_all:
                continue
            attendee.invited_at = now
            ids.append(attendee.id)
        await self.db.flush()
        return ids

    async def dashboard(self, exam: WorkshopExam) -> dict:
        attendees = await self.list_attendees(exam.id)
        submitted = [a for a in attendees if a.submitted_at is not None]
        started = [a for a in attendees if a.started_at is not None]
        percents = [a.score * 100 / a.total_marks for a in submitted if a.total_marks]
        return {
            "total_attendees": len(attendees),
            "invited": sum(1 for a in attendees if a.invited_at is not None),
            "not_started": len(attendees) - len(started),
            "in_progress": len(started) - len(submitted),
            "submitted": len(submitted),
            "certificates_sent": sum(1 for a in attendees if a.certificate_sent_at is not None),
            "average_score_percent": round(sum(percents) / len(percents), 1) if percents else None,
            "attendees": attendees,
        }

    # ---------------- public: attendee flow ----------------

    async def get_by_public_code(self, code: str) -> WorkshopExam:
        result = await self.db.execute(select(WorkshopExam).where(WorkshopExam.public_code == code))
        exam = result.scalar_one_or_none()
        if not exam:
            raise NotFoundError("Registration link")
        return exam

    async def join_info(self, exam: WorkshopExam) -> dict:
        question_count, _ = await self.counts_for(exam.id)
        state = {
            WorkshopExamStatus.OPEN: "open",
            WorkshopExamStatus.DRAFT: "not_open",
            WorkshopExamStatus.CLOSED: "closed",
        }[exam.status]
        return {
            "title": exam.title,
            "description": exam.description,
            "duration_minutes": exam.duration_minutes,
            "question_count": question_count,
            "info_fields": exam.info_fields or [],
            "state": state,
        }

    async def register(
        self, exam: WorkshopExam, name: str, email: str, info: dict[str, str]
    ) -> WorkshopExamAttendee | None:
        """Self-registration from the shared link. Returns the new
        attendee, or None if that email is already registered for this
        exam (the caller then re-sends the existing personal link by
        email rather than creating, or revealing, anything)."""
        if exam.status != WorkshopExamStatus.OPEN:
            raise ValidationError("Registration isn't open for this exam right now.")
        name = " ".join(name.split())
        if not name:
            raise ValidationError("Please enter your name.")
        clean_info: dict[str, str] = {}
        for field in exam.info_fields or []:
            value = " ".join(str(info.get(field["key"], "")).split())
            if not value:
                if field.get("required", True):
                    raise ValidationError(f"Please fill in: {field['label']}")
                continue
            if len(value) > 255:
                raise ValidationError(f"{field['label']} is too long.")
            if field["type"] == "select" and value not in field.get("options", []):
                raise ValidationError(f"Please choose a valid option for: {field['label']}")
            clean_info[field["key"]] = value

        email = email.strip().lower()
        existing = (
            await self.db.execute(
                select(WorkshopExamAttendee).where(
                    WorkshopExamAttendee.exam_id == exam.id, WorkshopExamAttendee.email == email
                )
            )
        ).scalar_one_or_none()
        if existing:
            return None
        _, attendee_count = await self.counts_for(exam.id)
        if attendee_count >= _MAX_ATTENDEES:
            raise ValidationError("This exam has reached its registration limit.")
        attendee = WorkshopExamAttendee(
            exam_id=exam.id,
            name=name,
            email=email,
            info=clean_info,
            access_token=secrets.token_urlsafe(24),
        )
        self.db.add(attendee)
        await self.db.flush()
        return attendee

    async def resend_existing_link(self, exam: WorkshopExam, email: str) -> uuid.UUID | None:
        attendee = (
            await self.db.execute(
                select(WorkshopExamAttendee).where(
                    WorkshopExamAttendee.exam_id == exam.id,
                    WorkshopExamAttendee.email == email.strip().lower(),
                )
            )
        ).scalar_one_or_none()
        return attendee.id if attendee and attendee.submitted_at is None else None

    async def get_by_token(self, token: str) -> tuple[WorkshopExamAttendee, WorkshopExam]:
        result = await self.db.execute(
            select(WorkshopExamAttendee).where(WorkshopExamAttendee.access_token == token)
        )
        attendee = result.scalar_one_or_none()
        if not attendee:
            # Same answer for "no such token" as for anything else -- don't
            # confirm which tokens exist.
            raise NotFoundError("Exam link")
        exam = (
            await self.db.execute(select(WorkshopExam).where(WorkshopExam.id == attendee.exam_id))
        ).scalar_one()
        return attendee, exam

    @staticmethod
    def _deadline(attendee: WorkshopExamAttendee, exam: WorkshopExam) -> datetime | None:
        if attendee.started_at is None:
            return None
        return attendee.started_at + timedelta(minutes=exam.duration_minutes)

    def _remaining(self, attendee: WorkshopExamAttendee, exam: WorkshopExam) -> int | None:
        deadline = self._deadline(attendee, exam)
        if deadline is None:
            return None
        return max(0, int((deadline - _now()).total_seconds()))

    async def _finalize(self, attendee: WorkshopExamAttendee, questions: list[WorkshopExamQuestion]) -> None:
        answers = attendee.answers or {}
        score = 0
        total = 0
        for q in questions:
            total += q.marks
            # All-or-nothing: the picked set must equal the answer key
            # (for a single-answer question that is just "picked the one").
            if set(answers.get(str(q.id), [])) == set(q.correct_indices):
                score += q.marks
        attendee.score = score
        attendee.total_marks = total
        attendee.submitted_at = _now()
        await self.db.flush()

    async def _auto_finalize_if_expired(
        self, attendee: WorkshopExamAttendee, exam: WorkshopExam
    ) -> None:
        if attendee.started_at and attendee.submitted_at is None:
            if self._remaining(attendee, exam) == 0:
                await self._finalize(attendee, await self.list_questions(exam.id))

    async def public_info(self, attendee: WorkshopExamAttendee, exam: WorkshopExam) -> dict:
        await self._auto_finalize_if_expired(attendee, exam)
        question_count, _ = await self.counts_for(exam.id)
        if attendee.submitted_at is not None:
            state = "submitted"
        elif exam.status == WorkshopExamStatus.DRAFT:
            state = "not_open"
        elif exam.status == WorkshopExamStatus.CLOSED and attendee.started_at is None:
            state = "closed"
        elif attendee.started_at is not None:
            state = "in_progress"
        else:
            state = "ready"
        info = {
            "title": exam.title,
            "description": exam.description,
            "attendee_name": attendee.name,
            "duration_minutes": exam.duration_minutes,
            "question_count": question_count,
            "state": state,
            "remaining_seconds": self._remaining(attendee, exam) if state == "in_progress" else None,
        }
        if state == "submitted" and exam.show_result:
            info["score"] = attendee.score
            info["total_marks"] = attendee.total_marks
        return info

    async def start(self, attendee: WorkshopExamAttendee, exam: WorkshopExam) -> dict:
        await self._auto_finalize_if_expired(attendee, exam)
        if attendee.submitted_at is not None:
            raise ValidationError("You have already submitted this exam.")
        if exam.status != WorkshopExamStatus.OPEN and attendee.started_at is None:
            raise ValidationError("This exam isn't open right now.")
        if attendee.started_at is None:
            attendee.started_at = _now()
            await self.db.flush()
        questions = await self.list_questions(exam.id)
        # Same order and same option order on every reload for one attendee
        # (seeded by their token), different between attendees -- cheap
        # protection against neighbours copying answers in a shared room.
        order = random.Random(attendee.access_token)
        shuffled = list(questions)
        order.shuffle(shuffled)
        payload = []
        for q in shuffled:
            options = list(enumerate(q.options))
            random.Random(f"{attendee.access_token}:{q.id}").shuffle(options)
            payload.append(
                {
                    "id": q.id,
                    "text": q.text,
                    "marks": q.marks,
                    "allow_multiple": q.allow_multiple,
                    "options": [{"index": i, "text": text} for i, text in options],
                }
            )
        return {
            "remaining_seconds": self._remaining(attendee, exam) or 0,
            "questions": payload,
            "saved_answers": {k: list(v) for k, v in (attendee.answers or {}).items()},
        }

    async def save_answers(
        self, attendee: WorkshopExamAttendee, exam: WorkshopExam, answers: dict[str, list[int]]
    ) -> None:
        if attendee.submitted_at is not None or attendee.started_at is None:
            return
        remaining = self._remaining(attendee, exam)
        if remaining is not None and remaining <= 0 and (
            _now() - self._deadline(attendee, exam) > _SUBMIT_GRACE
        ):
            return
        by_id = {str(q.id): q for q in await self.list_questions(exam.id)}
        merged = dict(attendee.answers or {})
        for key, picked in answers.items():
            question = by_id.get(key)
            if question is None:
                continue
            # Drop anything that is not a real option, dedupe, and keep a
            # single-answer question to one pick, whatever the client sent.
            clean = sorted({i for i in picked if 0 <= i < len(question.options)})
            if not question.allow_multiple:
                clean = clean[:1]
            merged[key] = clean
        attendee.answers = merged
        await self.db.flush()

    async def submit(
        self, attendee: WorkshopExamAttendee, exam: WorkshopExam, answers: dict[str, list[int]]
    ) -> dict:
        if attendee.submitted_at is None:
            if attendee.started_at is None:
                raise ValidationError("You haven't started this exam yet.")
            await self.save_answers(attendee, exam, answers)
            await self._finalize(attendee, await self.list_questions(exam.id))
        result: dict = {"submitted": True}
        if exam.show_result:
            result["score"] = attendee.score
            result["total_marks"] = attendee.total_marks
        return result

    # ---------------- certificates ----------------

    async def _new_certificate_number(self) -> str:
        year = _now().year
        while True:
            number = f"WS-{year}-{secrets.token_hex(4).upper()}"
            exists = (
                await self.db.execute(
                    select(WorkshopExamAttendee.id).where(WorkshopExamAttendee.certificate_number == number)
                )
            ).first()
            if not exists:
                return number

    async def dispatch_certificates(self, exam: WorkshopExam) -> list[uuid.UUID]:
        """Everyone who actually wrote the exam gets a certificate: anyone
        who submitted, plus anyone who started but never pressed submit
        (finalized here from their autosaved answers). Returns the
        attendee ids whose certificate email still needs sending."""
        attendees = await self.list_attendees(exam.id)
        questions = await self.list_questions(exam.id)
        pending: list[uuid.UUID] = []
        for attendee in attendees:
            if attendee.submitted_at is None and attendee.started_at is not None:
                await self._finalize(attendee, questions)
            if attendee.submitted_at is None:
                continue
            if attendee.certificate_number is None:
                attendee.certificate_number = await self._new_certificate_number()
                await self.db.flush()
            if attendee.certificate_sent_at is None:
                pending.append(attendee.id)
        exam.certificates_dispatched_at = _now()
        await self.db.flush()
        return pending

    async def due_exams(self) -> list[WorkshopExam]:
        result = await self.db.execute(
            select(WorkshopExam).where(
                WorkshopExam.certificate_release_at.is_not(None),
                WorkshopExam.certificate_release_at <= _now(),
                WorkshopExam.certificates_dispatched_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def verify_certificate(self, certificate_number: str) -> dict:
        result = await self.db.execute(
            select(WorkshopExamAttendee).where(
                WorkshopExamAttendee.certificate_number == certificate_number
            )
        )
        attendee = result.scalar_one_or_none()
        if not attendee:
            return {"valid": False}
        exam = (
            await self.db.execute(select(WorkshopExam).where(WorkshopExam.id == attendee.exam_id))
        ).scalar_one()
        return {
            "valid": True,
            "attendee_name": attendee.name,
            "exam_title": exam.title,
            "issued_at": attendee.submitted_at,
        }
