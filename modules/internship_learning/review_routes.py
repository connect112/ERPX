"""Routes for project reviews, final marks and awards (staff), and a student's own awards."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.internship_learning.project_service import ProjectService
from modules.internship_learning.review_schemas import (
    AwardOut,
    AwardRequest,
    AwardUpdateRequest,
    FinalRequest,
    GrantRequest,
    MyAward,
    ReviewRequest,
    ReviewRow,
)
from modules.internship_learning.review_service import AwardService, ReviewService
from modules.internship_learning.schemas import MessageResponse
from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship
from modules.our_internships.service import OurInternshipService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()
my_awards_router = APIRouter()
my_router = APIRouter()


async def _project(db: AsyncSession, internship_id: uuid.UUID, project_id: uuid.UUID, organization_id: uuid.UUID):
    return await ProjectService(db).get(internship_id, project_id, organization_id)


# ============================ reviews and final marks ============================


@router.get("/{internship_id}/projects/{project_id}/reviews", response_model=list[ReviewRow])
async def list_reviews(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    project = await _project(db, internship_id, project_id, organization_id)
    return await ReviewService(db).rows(project)


@router.post(
    "/{internship_id}/projects/{project_id}/submissions/{selection_id}/reviews",
    response_model=ReviewRow,
    status_code=status.HTTP_201_CREATED,
)
async def add_review(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    payload: ReviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    project = await _project(db, internship_id, project_id, organization_id)
    service = ReviewService(db)
    await service.add_review(project, selection_id, user.id, payload)
    return await service.row(project, selection_id)


@router.put("/{internship_id}/projects/{project_id}/reviews/{review_id}", response_model=ReviewRow)
async def update_review(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    payload: ReviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    project = await _project(db, internship_id, project_id, organization_id)
    service = ReviewService(db)
    review = await service.update_review(project, review_id, payload)
    _, submission = await service._review(project, review.id)
    return await service.row(project, submission.selection_id)


@router.delete("/{internship_id}/projects/{project_id}/reviews/{review_id}", response_model=ReviewRow)
async def delete_review(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    project = await _project(db, internship_id, project_id, organization_id)
    service = ReviewService(db)
    submission = await service.delete_review(project, review_id)
    return await service.row(project, submission.selection_id)


@router.put("/{internship_id}/projects/{project_id}/submissions/{selection_id}/final", response_model=ReviewRow)
async def publish_final(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    payload: FinalRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Set the final marks (the average of the reviews unless given) and publish the result to the student."""
    project = await _project(db, internship_id, project_id, organization_id)
    service = ReviewService(db)
    await service.finalize(project, selection_id, payload.final_marks, payload.feedback, user.id)
    return await service.row(project, selection_id)


@router.delete("/{internship_id}/projects/{project_id}/submissions/{selection_id}/final", response_model=ReviewRow)
async def unpublish_final(
    internship_id: uuid.UUID,
    project_id: uuid.UUID,
    selection_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    project = await _project(db, internship_id, project_id, organization_id)
    service = ReviewService(db)
    await service.unfinalize(project, selection_id)
    return await service.row(project, selection_id)


# ============================ awards ============================


@router.get("/{internship_id}/awards", response_model=list[AwardOut])
async def list_awards(
    internship_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.view")),
    db: AsyncSession = Depends(get_db),
):
    await OurInternshipService(db).get(internship_id, organization_id)
    return await AwardService(db).listing(internship_id, organization_id)


@router.post("/{internship_id}/awards", response_model=AwardOut, status_code=status.HTTP_201_CREATED)
async def create_award(
    internship_id: uuid.UUID,
    payload: AwardRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    await OurInternshipService(db).get(internship_id, organization_id)
    service = AwardService(db)
    award = await service.create(internship_id, organization_id, payload.name, payload.description)
    return next(a for a in await service.listing(internship_id, organization_id) if a["id"] == award.id)


@router.patch("/{internship_id}/awards/{award_id}", response_model=AwardOut)
async def update_award(
    internship_id: uuid.UUID,
    award_id: uuid.UUID,
    payload: AwardUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AwardService(db)
    award = await service.get(internship_id, award_id, organization_id)
    await service.update(award, payload.model_dump(exclude_unset=True))
    return next(a for a in await service.listing(internship_id, organization_id) if a["id"] == award.id)


@router.delete("/{internship_id}/awards/{award_id}", response_model=MessageResponse)
async def delete_award(
    internship_id: uuid.UUID,
    award_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AwardService(db)
    await service.delete(await service.get(internship_id, award_id, organization_id))
    return MessageResponse(message="The award was deleted and taken from every student who held it.")


@router.put("/{internship_id}/awards/{award_id}/grants", response_model=AwardOut)
async def grant_award(
    internship_id: uuid.UUID,
    award_id: uuid.UUID,
    payload: GrantRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AwardService(db)
    award = await service.get(internship_id, award_id, organization_id)
    await service.grant(award, payload.selection_id, payload.note, user.id)
    return next(a for a in await service.listing(internship_id, organization_id) if a["id"] == award.id)


@router.delete("/{internship_id}/awards/{award_id}/grants/{selection_id}", response_model=AwardOut)
async def revoke_award(
    internship_id: uuid.UUID,
    award_id: uuid.UUID,
    selection_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("our_internships.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AwardService(db)
    award = await service.get(internship_id, award_id, organization_id)
    await service.revoke(award, selection_id)
    return next(a for a in await service.listing(internship_id, organization_id) if a["id"] == award.id)


# ============================ the student's awards ============================


@my_awards_router.get("", response_model=list[MyAward])
async def my_awards(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Every award the student holds, across their internships (for the profile and dashboard)."""
    selection_ids = (
        (
            await db.execute(
                select(InternshipSelection.id).where(
                    InternshipSelection.lms_student_id == student.id,
                    InternshipSelection.lms_status == LmsStatus.GRANTED,
                    InternshipSelection.organization_id == student.organization_id,
                )
            )
        )
        .scalars()
        .all()
    )
    service = AwardService(db)
    grants = await service.mine(list(selection_ids))
    internships = {
        i.id: i
        for i in (
            await db.execute(select(OurInternship).where(OurInternship.id.in_({s.internship_id for _, _, s in grants} or {uuid.uuid4()})))
        ).scalars()
    }
    return [
        MyAward(
            id=a.id,
            internship_id=s.internship_id,
            internship_title=internships[s.internship_id].title,
            name=a.name,
            description=a.description,
            note=g.note,
            granted_at=g.granted_at,
        )
        for g, a, s in grants
    ]


@my_router.get("/{internship_id}/awards", response_model=list[MyAward])
async def my_internship_awards(
    internship_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = AwardService(db)
    selection = await service.learning.selection_for_student(student, internship_id)
    internship = await OurInternshipService(db).get(internship_id, student.organization_id)
    return [
        MyAward(
            id=a.id,
            internship_id=internship_id,
            internship_title=internship.title,
            name=a.name,
            description=a.description,
            note=g.note,
            granted_at=g.granted_at,
        )
        for g, a, _ in await service.mine([selection.id])
    ]
