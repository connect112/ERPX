import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.examinations.question_bank.schemas import (
    MessageResponse,
    QuestionCreateRequest,
    QuestionPublic,
    QuestionUpdateRequest,
)
from modules.examinations.question_bank.service import QuestionService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=QuestionPublic, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.question_bank.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionService(db)
    question = await service.create_question(organization_id, **payload.model_dump())
    return QuestionPublic.model_validate(question)


@router.get("", response_model=list[QuestionPublic])
async def list_questions(
    course_id: uuid.UUID | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.question_bank.view")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionService(db)
    questions = await service.list_questions(organization_id, course_id)
    return [QuestionPublic.model_validate(q) for q in questions]


@router.get("/{question_id}", response_model=QuestionPublic)
async def get_question(
    question_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.question_bank.view")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionService(db)
    question = await service.get_question(question_id, organization_id)
    return QuestionPublic.model_validate(question)


@router.patch("/{question_id}", response_model=QuestionPublic)
async def update_question(
    question_id: uuid.UUID,
    payload: QuestionUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.question_bank.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionService(db)
    question = await service.update_question(
        question_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return QuestionPublic.model_validate(question)


@router.delete("/{question_id}", response_model=MessageResponse)
async def delete_question(
    question_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.question_bank.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = QuestionService(db)
    await service.delete_question(question_id, organization_id)
    return MessageResponse(message="Question deleted successfully.")
