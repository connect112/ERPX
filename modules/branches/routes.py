import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.branches.schemas import (
    BranchCreateRequest,
    BranchPublic,
    BranchUpdateRequest,
    MessageResponse,
)
from modules.branches.service import BranchService

router = APIRouter()


@router.post("", response_model=BranchPublic, status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreateRequest,
    user: User = Depends(require_permissions("branches.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BranchService(db)
    branch = await service.create_branch(**payload.model_dump())
    return BranchPublic.model_validate(branch)


@router.get("", response_model=list[BranchPublic])
async def list_branches(
    organization_id: uuid.UUID,
    user: User = Depends(require_permissions("branches.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BranchService(db)
    branches = await service.list_branches(organization_id)
    return [BranchPublic.model_validate(b) for b in branches]


@router.get("/{branch_id}", response_model=BranchPublic)
async def get_branch(
    branch_id: uuid.UUID,
    user: User = Depends(require_permissions("branches.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BranchService(db)
    branch = await service.get_branch(branch_id)
    return BranchPublic.model_validate(branch)


@router.patch("/{branch_id}", response_model=BranchPublic)
async def update_branch(
    branch_id: uuid.UUID,
    payload: BranchUpdateRequest,
    user: User = Depends(require_permissions("branches.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BranchService(db)
    branch = await service.update_branch(branch_id, **payload.model_dump(exclude_unset=True))
    return BranchPublic.model_validate(branch)


@router.delete("/{branch_id}", response_model=MessageResponse)
async def delete_branch(
    branch_id: uuid.UUID,
    user: User = Depends(require_permissions("branches.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BranchService(db)
    await service.delete_branch(branch_id)
    return MessageResponse(message="Branch deleted successfully.")
