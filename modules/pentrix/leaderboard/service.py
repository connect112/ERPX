"""
Leaderboard — computed live, same "no redundant table" approach as
Results (Examinations) and Certificate verification (LMS): a student's
rank is derived from Submissions (points earned) minus HintUnlocks
(points spent), never cached, so it can never drift out of sync with
the underlying solves.
"""

import uuid

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.flags.models import Submission
from modules.pentrix.hints.models import Hint, HintUnlock
from modules.students.models import Student


class LeaderboardEntry(BaseModel):
    student_id: uuid.UUID
    student_name: str
    student_code: str
    challenges_solved: int
    points_earned: int
    points_spent_on_hints: int
    net_score: int


class LeaderboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_leaderboard(
        self, organization_id: uuid.UUID, limit: int = 50
    ) -> list[LeaderboardEntry]:
        # Points earned + challenges solved, aggregated per student.
        earned_result = await self.db.execute(
            select(
                Submission.student_id,
                func.count(Submission.id).label("challenges_solved"),
                func.coalesce(func.sum(Submission.points_awarded), 0).label("points_earned"),
            )
            .join(Student, Student.id == Submission.student_id)
            .where(Student.organization_id == organization_id, Student.deleted_at.is_(None))
            .group_by(Submission.student_id)
        )
        earned_by_student = {row.student_id: row for row in earned_result.all()}

        # Points spent on hints, aggregated per student.
        spent_result = await self.db.execute(
            select(
                HintUnlock.student_id,
                func.coalesce(func.sum(Hint.point_cost), 0).label("points_spent"),
            )
            .join(Hint, Hint.id == HintUnlock.hint_id)
            .join(Student, Student.id == HintUnlock.student_id)
            .where(Student.organization_id == organization_id, Student.deleted_at.is_(None))
            .group_by(HintUnlock.student_id)
        )
        spent_by_student = {row.student_id: row.points_spent for row in spent_result.all()}

        active_student_ids = set(earned_by_student.keys()) | set(spent_by_student.keys())
        if not active_student_ids:
            return []

        students_result = await self.db.execute(
            select(Student).where(Student.id.in_(active_student_ids))
        )
        students_by_id = {s.id: s for s in students_result.scalars().all()}

        entries: list[LeaderboardEntry] = []
        for student_id in active_student_ids:
            student = students_by_id.get(student_id)
            if not student:
                continue
            earned_row = earned_by_student.get(student_id)
            points_earned = earned_row.points_earned if earned_row else 0
            challenges_solved = earned_row.challenges_solved if earned_row else 0
            points_spent = spent_by_student.get(student_id, 0)

            entries.append(
                LeaderboardEntry(
                    student_id=student.id,
                    student_name=student.full_name,
                    student_code=student.student_code,
                    challenges_solved=challenges_solved,
                    points_earned=points_earned,
                    points_spent_on_hints=points_spent,
                    net_score=points_earned - points_spent,
                )
            )

        entries.sort(key=lambda e: e.net_score, reverse=True)
        return entries[:limit]
