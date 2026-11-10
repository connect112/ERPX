"""
Courses module — top-level router aggregator.

Mounted at /courses in the main API router. Categories and Learning
Paths get their own sub-prefixes; Courses, Chapters, Lessons, and
Resources share the root since chapters/lessons/resources already embed
their full nested path (/{course_id}/chapters/{chapter_id}/...).
"""

from fastapi import APIRouter, Depends

from modules.courses.categories.routes import router as categories_router
from modules.courses.chapters.routes import router as chapters_router
from modules.courses.learning_paths.routes import router as learning_paths_router
from modules.courses.lessons.routes import router as lessons_router
from modules.courses.resources.routes import router as resources_router
from modules.courses.routes import router as courses_router
from modules.lms.enrollment.access import student_course_guard

router = APIRouter()

router.include_router(categories_router, prefix="/categories", tags=["Courses - Categories"])
router.include_router(
    learning_paths_router, prefix="/learning-paths", tags=["Courses - Learning Paths"]
)
router.include_router(courses_router, tags=["Courses"])
# a student reads chapters, lessons and resources only through a live enrolment (see modules/lms/enrollment/access.py)
router.include_router(chapters_router, tags=["Courses - Chapters"], dependencies=[Depends(student_course_guard)])
router.include_router(lessons_router, tags=["Courses - Lessons"], dependencies=[Depends(student_course_guard)])
router.include_router(resources_router, tags=["Courses - Resources"], dependencies=[Depends(student_course_guard)])
