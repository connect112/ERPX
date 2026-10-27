"""
Project reviews, final marks and awards.

A submission can be reviewed several times; each review is marked on the project's factors (or one score). Staff then set
the final marks (by default the average of the reviews) and publish them: students see reviews and the final result only
after that, and cannot change their submission afterwards.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from modules.authentication.models import User
from modules.internship_learning.award_models import AwardGrant, InternshipAward
from modules.internship_learning.project_models import InternshipProject, ProjectReview, ProjectSubmission
from modules.internship_learning.review_schemas import ReviewRequest
from modules.internship_learning.service import InternshipLearningService
from modules.our_internships.models import InternshipSelection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def average_of(totals: list[float]) -> float | None:
    return round(sum(totals) / len(totals), 2) if totals else None


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.learning = InternshipLearningService(db)

    async def _submission(self, project: InternshipProject, selection_id: uuid.UUID) -> ProjectSubmission:
        submission = (
            await self.db.execute(
                select(ProjectSubmission).where(
                    ProjectSubmission.project_id == project.id, ProjectSubmission.selection_id == selection_id
                )
            )
        ).scalar_one_or_none()
        if not submission:
            raise NotFoundError("Submission", selection_id)
        return submission

    async def reviews_for(self, submission_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ProjectReview]]:
        if not submission_ids:
            return {}
        rows = await self.db.execute(
            select(ProjectReview).where(ProjectReview.submission_id.in_(submission_ids)).order_by(ProjectReview.created_at)
        )
        grouped: dict[uuid.UUID, list[ProjectReview]] = {}
        for review in rows.scalars().all():
            grouped.setdefault(review.submission_id, []).append(review)
        return grouped

    async def _names(self, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        rows = await self.db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))
        return {uid: name for uid, name in rows.all()}

    def review_out(self, review: ProjectReview, names: dict[uuid.UUID, str]) -> dict:
        return {
            "id": review.id,
            "label": review.label,
            "reviewer_name": names.get(review.reviewer_user_id) if review.reviewer_user_id else None,
            "factor_scores": review.factor_scores,
            "total": float(review.total),
            "max_total": review.max_total,
            "feedback": review.feedback,
            "created_at": review.created_at,
            "updated_at": review.updated_at,
        }

    async def rows(self, project: InternshipProject) -> list[dict]:
        """Every enrolled student who handed this project in, with reviews and result."""
        enrolled = await self.learning.enrolled(project.internship_id)
        submissions = {
            s.selection_id: s
            for s in (await self.db.execute(select(ProjectSubmission).where(ProjectSubmission.project_id == project.id))).scalars()
        }
        reviews = await self.reviews_for([s.id for s in submissions.values()])
        names = await self._names({r.reviewer_user_id for rs in reviews.values() for r in rs if r.reviewer_user_id})
        out = []
        for selection, person in enrolled:
            sub = submissions.get(selection.id)
            if not sub:
                continue
            mine = reviews.get(sub.id, [])
            out.append(
                {
                    "selection_id": selection.id,
                    "student_name": person.name,
                    "student_email": person.email,
                    "method": sub.method,
                    "submitted_at": sub.submitted_at,
                    "is_late": sub.is_late,
                    "reviews": [self.review_out(r, names) for r in mine],
                    "average": average_of([float(r.total) for r in mine]),
                    "max_marks": project.max_marks,
                    "final_marks": float(sub.final_marks) if sub.final_marks is not None else None,
                    "final_feedback": sub.final_feedback,
                    "final_published_at": sub.final_published_at,
                }
            )
        return out

    async def row(self, project: InternshipProject, selection_id: uuid.UUID) -> dict:
        return next(r for r in await self.rows(project) if r["selection_id"] == selection_id)

    def _score(self, project: InternshipProject, req: ReviewRequest) -> tuple[dict | None, float]:
        if project.review_factors:
            given = req.factor_scores or {}
            factors = {f["id"]: f for f in project.review_factors}
            if set(given) - set(factors):
                raise ValidationError("Some marks are for factors that are not on this project.")
            for factor_id, marks in given.items():
                if marks < 0 or marks > factors[factor_id]["max_marks"]:
                    raise ValidationError(f"{factors[factor_id]['name']}: marks must be between 0 and {factors[factor_id]['max_marks']}.")
            scores = {factor_id: given.get(factor_id, 0) for factor_id in factors}
            return scores, round(sum(scores.values()), 2)
        if req.score is None:
            raise ValidationError("Please enter the marks.")
        if req.score > project.max_marks:
            raise ValidationError(f"Marks cannot be more than {project.max_marks}.")
        return None, round(req.score, 2)

    async def add_review(
        self, project: InternshipProject, selection_id: uuid.UUID, user_id: uuid.UUID, req: ReviewRequest
    ) -> ProjectReview:
        submission = await self._submission(project, selection_id)
        if submission.final_published_at:
            raise ConflictError("The final result has been published. Unpublish it before adding another review.")
        scores, total = self._score(project, req)
        review = ProjectReview(
            organization_id=project.organization_id,
            submission_id=submission.id,
            reviewer_user_id=user_id,
            label=req.label,
            factor_scores=scores,
            total=total,
            max_total=project.max_marks,
            feedback=(req.feedback or "").strip() or None,
        )
        self.db.add(review)
        await self.db.flush()
        return review

    async def _review(self, project: InternshipProject, review_id: uuid.UUID) -> tuple[ProjectReview, ProjectSubmission]:
        row = (
            await self.db.execute(
                select(ProjectReview, ProjectSubmission)
                .join(ProjectSubmission, ProjectSubmission.id == ProjectReview.submission_id)
                .where(ProjectReview.id == review_id, ProjectSubmission.project_id == project.id)
            )
        ).first()
        if not row:
            raise NotFoundError("Review", review_id)
        return row[0], row[1]

    async def update_review(self, project: InternshipProject, review_id: uuid.UUID, req: ReviewRequest) -> ProjectReview:
        review, submission = await self._review(project, review_id)
        if submission.final_published_at:
            raise ConflictError("The final result has been published. Unpublish it before changing a review.")
        scores, total = self._score(project, req)
        review.label, review.factor_scores, review.total = req.label, scores, total
        review.max_total = project.max_marks
        review.feedback = (req.feedback or "").strip() or None
        await self.db.flush()
        return review

    async def delete_review(self, project: InternshipProject, review_id: uuid.UUID) -> ProjectSubmission:
        review, submission = await self._review(project, review_id)
        if submission.final_published_at:
            raise ConflictError("The final result has been published. Unpublish it before deleting a review.")
        await self.db.delete(review)
        await self.db.flush()
        return submission

    async def finalize(
        self,
        project: InternshipProject,
        selection_id: uuid.UUID,
        final_marks: float | None,
        feedback: str | None,
        user_id: uuid.UUID,
    ) -> ProjectSubmission:
        submission = await self._submission(project, selection_id)
        reviews = (await self.reviews_for([submission.id])).get(submission.id, [])
        if final_marks is None:
            average = average_of([float(r.total) for r in reviews])
            if average is None:
                raise ValidationError("Write at least one review, or enter the final marks yourself.")
            final_marks = average
        if final_marks > project.max_marks:
            raise ValidationError(f"Marks cannot be more than {project.max_marks}.")
        submission.final_marks = round(final_marks, 2)
        submission.final_feedback = (feedback or "").strip() or None
        submission.final_published_at = _now()
        submission.finalized_by_user_id = user_id
        await self.db.flush()
        return submission

    async def unfinalize(self, project: InternshipProject, selection_id: uuid.UUID) -> ProjectSubmission:
        submission = await self._submission(project, selection_id)
        submission.final_marks = None
        submission.final_feedback = None
        submission.final_published_at = None
        submission.finalized_by_user_id = None
        await self.db.flush()
        return submission

    async def result_for_student(self, project: InternshipProject, submission: ProjectSubmission) -> dict | None:
        """The published result a student may see, or None until staff publish it."""
        if not submission.final_published_at:
            return None
        reviews = (await self.reviews_for([submission.id])).get(submission.id, [])
        return {
            "final_marks": float(submission.final_marks) if submission.final_marks is not None else None,
            "max_marks": project.max_marks,
            "feedback": submission.final_feedback,
            "published_at": submission.final_published_at,
            "reviews": [
                {
                    "label": r.label,
                    "total": float(r.total),
                    "max_total": r.max_total,
                    "factor_scores": r.factor_scores,
                    "feedback": r.feedback,
                    "reviewed_at": r.updated_at,
                }
                for r in reviews
            ],
        }


class AwardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.learning = InternshipLearningService(db)

    async def get(self, internship_id: uuid.UUID, award_id: uuid.UUID, organization_id: uuid.UUID) -> InternshipAward:
        award = (
            await self.db.execute(
                select(InternshipAward).where(
                    InternshipAward.id == award_id,
                    InternshipAward.internship_id == internship_id,
                    InternshipAward.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if not award:
            raise NotFoundError("Award", award_id)
        return award

    async def create(self, internship_id: uuid.UUID, organization_id: uuid.UUID, name: str, description: str | None) -> InternshipAward:
        taken = (
            await self.db.execute(
                select(InternshipAward.id).where(
                    InternshipAward.internship_id == internship_id, InternshipAward.name.ilike(name)
                )
            )
        ).first()
        if taken:
            raise ConflictError("This internship already has an award with that name.")
        award = InternshipAward(
            organization_id=organization_id, internship_id=internship_id, name=name, description=(description or "").strip() or None
        )
        self.db.add(award)
        await self.db.flush()
        return award

    async def update(self, award: InternshipAward, fields: dict) -> InternshipAward:
        if fields.get("name"):
            name = " ".join(fields["name"].split())
            clash = (
                await self.db.execute(
                    select(InternshipAward.id).where(
                        InternshipAward.internship_id == award.internship_id,
                        InternshipAward.name.ilike(name),
                        InternshipAward.id != award.id,
                    )
                )
            ).first()
            if clash:
                raise ConflictError("This internship already has an award with that name.")
            award.name = name
        if "description" in fields:
            award.description = (fields["description"] or "").strip() or None
        await self.db.flush()
        return award

    async def delete(self, award: InternshipAward) -> None:
        await self.db.delete(award)
        await self.db.flush()

    async def listing(self, internship_id: uuid.UUID, organization_id: uuid.UUID) -> list[dict]:
        awards = (
            await self.db.execute(
                select(InternshipAward)
                .where(InternshipAward.internship_id == internship_id, InternshipAward.organization_id == organization_id)
                .order_by(InternshipAward.created_at)
            )
        ).scalars().all()
        people = {s.id: p for s, p in await self.learning.enrolled(internship_id)}
        grants: dict[uuid.UUID, list[AwardGrant]] = {}
        if awards:
            for g in (
                await self.db.execute(
                    select(AwardGrant).where(AwardGrant.award_id.in_([a.id for a in awards])).order_by(AwardGrant.granted_at)
                )
            ).scalars():
                grants.setdefault(g.award_id, []).append(g)
        return [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "grants": [
                    {
                        "selection_id": g.selection_id,
                        "student_name": people[g.selection_id].name,
                        "student_email": people[g.selection_id].email,
                        "note": g.note,
                        "granted_at": g.granted_at,
                    }
                    for g in grants.get(a.id, [])
                    # a student whose access was taken away no longer appears, though the grant is kept
                    if g.selection_id in people
                ],
            }
            for a in awards
        ]

    async def grant(self, award: InternshipAward, selection_id: uuid.UUID, note: str | None, user_id: uuid.UUID) -> AwardGrant:
        enrolled = {s.id for s, _ in await self.learning.enrolled(award.internship_id)}
        if selection_id not in enrolled:
            raise ValidationError("Awards can only be given to students who have LMS access on this internship.")
        existing = (
            await self.db.execute(
                select(AwardGrant).where(AwardGrant.award_id == award.id, AwardGrant.selection_id == selection_id)
            )
        ).scalar_one_or_none()
        if existing:
            existing.note = (note or "").strip() or None
            await self.db.flush()
            return existing
        grant = AwardGrant(
            organization_id=award.organization_id,
            award_id=award.id,
            selection_id=selection_id,
            note=(note or "").strip() or None,
            granted_at=_now(),
            granted_by_user_id=user_id,
        )
        self.db.add(grant)
        await self.db.flush()
        return grant

    async def revoke(self, award: InternshipAward, selection_id: uuid.UUID) -> None:
        grant = (
            await self.db.execute(
                select(AwardGrant).where(AwardGrant.award_id == award.id, AwardGrant.selection_id == selection_id)
            )
        ).scalar_one_or_none()
        if not grant:
            raise NotFoundError("Award grant", selection_id)
        await self.db.delete(grant)
        await self.db.flush()

    async def mine(self, selection_ids: list[uuid.UUID]) -> list[tuple[AwardGrant, InternshipAward, InternshipSelection]]:
        """Awards given to a student, across the internships they are on."""
        if not selection_ids:
            return []
        rows = await self.db.execute(
            select(AwardGrant, InternshipAward, InternshipSelection)
            .join(InternshipAward, InternshipAward.id == AwardGrant.award_id)
            .join(InternshipSelection, InternshipSelection.id == AwardGrant.selection_id)
            .where(AwardGrant.selection_id.in_(selection_ids))
            .order_by(AwardGrant.granted_at.desc())
        )
        return [(g, a, s) for g, a, s in rows.all()]
