import hashlib
import hmac
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.pentrix.challenges.repository import ChallengeRepository
from modules.pentrix.flags.models import Flag, Submission
from modules.pentrix.flags.repository import FlagRepository, SubmissionRepository
from modules.pentrix.flags.schemas import SubmissionResultResponse
from modules.students.repository import StudentRepository

logger = get_logger(__name__)


def _hash_flag(flag_value: str) -> str:
    return hashlib.sha256(flag_value.strip().encode("utf-8")).hexdigest()


class FlagService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.flag_repo = FlagRepository(db)
        self.submission_repo = SubmissionRepository(db)
        self.challenge_repo = ChallengeRepository(db)
        self.student_repo = StudentRepository(db)

    async def set_flag(
        self, challenge_id: uuid.UUID, organization_id: uuid.UUID, flag_value: str
    ) -> Flag:
        challenge = await self.challenge_repo.get_by_id(challenge_id, organization_id)
        if not challenge:
            raise NotFoundError("Challenge", challenge_id)
        flag = await self.flag_repo.upsert(challenge_id, _hash_flag(flag_value))
        logger.info("flag_set", challenge_id=str(challenge_id))
        return flag

    async def submit(
        self,
        challenge_id: uuid.UUID,
        organization_id: uuid.UUID,
        student_id: uuid.UUID,
        flag_value: str,
    ) -> SubmissionResultResponse:
        challenge = await self.challenge_repo.get_by_id(challenge_id, organization_id)
        if not challenge:
            raise NotFoundError("Challenge", challenge_id)
        student = await self.student_repo.get_by_id(student_id, organization_id)
        if not student:
            raise NotFoundError("Student", student_id)

        existing = await self.submission_repo.get(challenge_id, student_id)
        if existing:
            return SubmissionResultResponse(correct=True, already_solved=True, points_awarded=0)

        flag = await self.flag_repo.get_by_challenge(challenge_id)
        if not flag:
            raise NotFoundError("Flag for this challenge (not yet configured)", challenge_id)

        submitted_hash = _hash_flag(flag_value)
        is_correct = hmac.compare_digest(submitted_hash, flag.flag_hash)

        if not is_correct:
            logger.info(
                "flag_submission_incorrect", challenge_id=str(challenge_id), student_id=str(student_id)
            )
            return SubmissionResultResponse(correct=False)

        await self.submission_repo.create(
            challenge_id=challenge_id, student_id=student_id, points_awarded=challenge.points
        )
        logger.info(
            "flag_submission_correct",
            challenge_id=str(challenge_id),
            student_id=str(student_id),
            points=challenge.points,
        )
        return SubmissionResultResponse(correct=True, points_awarded=challenge.points)

    async def list_solves_for_student(self, student_id: uuid.UUID) -> list[Submission]:
        return await self.submission_repo.list_for_student(student_id)
