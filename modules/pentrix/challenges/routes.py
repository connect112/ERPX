import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.pentrix.challenges.schemas import (
    ChallengeCreateRequest,
    ChallengePublic,
    ChallengeUpdateRequest,
    MessageResponse,
)
from modules.pentrix.challenges.service import ChallengeService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=ChallengePublic, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    payload: ChallengeCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.challenges.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ChallengeService(db)
    challenge = await service.create_challenge(organization_id, **payload.model_dump())
    return ChallengePublic.model_validate(challenge)


@router.get("", response_model=list[ChallengePublic])
async def list_challenges(
    category: str | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.challenges.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ChallengeService(db)
    challenges = await service.list_challenges(organization_id, category)
    return [ChallengePublic.model_validate(c) for c in challenges]


@router.get("/{challenge_id}", response_model=ChallengePublic)
async def get_challenge(
    challenge_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.challenges.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ChallengeService(db)
    challenge = await service.get_challenge(challenge_id, organization_id)
    return ChallengePublic.model_validate(challenge)


@router.patch("/{challenge_id}", response_model=ChallengePublic)
async def update_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengeUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.challenges.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ChallengeService(db)
    challenge = await service.update_challenge(
        challenge_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return ChallengePublic.model_validate(challenge)


@router.delete("/{challenge_id}", response_model=MessageResponse)
async def delete_challenge(
    challenge_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("pentrix.challenges.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ChallengeService(db)
    await service.delete_challenge(challenge_id, organization_id)
    return MessageResponse(message="Challenge deleted successfully.")
