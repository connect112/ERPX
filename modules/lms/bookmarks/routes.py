import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.lms.bookmarks.schemas import BookmarkPublic, MessageResponse
from modules.lms.bookmarks.service import BookmarkService
from modules.students.dependencies import get_current_student
from modules.students.models import Student

router = APIRouter()


@router.get("/me", response_model=list[BookmarkPublic])
async def list_my_bookmarks(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = BookmarkService(db)
    return await service.list_my_bookmarks(student)


@router.post("/me/{lesson_id}", status_code=status.HTTP_201_CREATED, response_model=MessageResponse)
async def add_my_bookmark(
    lesson_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = BookmarkService(db)
    await service.add_bookmark(student, lesson_id)
    return MessageResponse(message="Lesson bookmarked.")


@router.delete("/me/{lesson_id}", response_model=MessageResponse)
async def remove_my_bookmark(
    lesson_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = BookmarkService(db)
    await service.remove_bookmark(student, lesson_id)
    return MessageResponse(message="Bookmark removed.")
