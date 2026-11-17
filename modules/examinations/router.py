"""
Examinations module — top-level router aggregator.

Mounted at /examinations. Question Bank and Results get their own
sub-prefixes; Exams, Evaluation, Practicals, and Viva share the root
since they already embed their full nested path
(/courses/{course_id}/... or /exams/{exam_id}/...).
"""

from fastapi import APIRouter, Depends

from modules.examinations.evaluation.routes import router as evaluation_router
from modules.examinations.exams.routes import router as exams_router
from modules.examinations.practicals.routes import router as practicals_router
from modules.examinations.question_bank.routes import router as question_bank_router
from modules.examinations.results.routes import router as results_router
from modules.examinations.viva.routes import router as viva_router
from modules.lms.enrollment.access import student_course_guard

router = APIRouter()

router.include_router(
    question_bank_router, prefix="/question-bank", tags=["Examinations - Question Bank"]
)
router.include_router(results_router, prefix="/results", tags=["Examinations - Results"])
# a student reaches a course's exams, practicals and viva only through a live enrolment in it (the same guard as the course content)
router.include_router(exams_router, tags=["Examinations - Exams"], dependencies=[Depends(student_course_guard)])
router.include_router(evaluation_router, tags=["Examinations - Evaluation"])
router.include_router(practicals_router, tags=["Examinations - Practicals"], dependencies=[Depends(student_course_guard)])
router.include_router(viva_router, tags=["Examinations - Viva"], dependencies=[Depends(student_course_guard)])
