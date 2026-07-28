"""
LMS module — top-level router aggregator.

Mounted at /lms. Enrollment, Progress, Certificates, Badges, and
Bookmarks get their own sub-prefixes; Assignments, Assessments, and Discussions share
the root since they already embed their full nested path
(/courses/{course_id}/...); Announcements sits at the root too.
"""

from fastapi import APIRouter

from modules.lms.announcements.routes import router as announcements_router
from modules.lms.assessments.routes import router as assessments_router
from modules.lms.assignments.routes import router as assignments_router
from modules.lms.badges.routes import router as badges_router
from modules.lms.bookmarks.routes import router as bookmarks_router
from modules.lms.certificates.routes import router as certificates_router
from modules.lms.discussions.routes import router as discussions_router
from modules.lms.enrollment.routes import router as enrollment_router
from modules.lms.progress.routes import router as progress_router
from modules.lms.transcripts.routes import router as transcripts_router

router = APIRouter()

router.include_router(enrollment_router, prefix="/enrollment", tags=["LMS - Enrollment"])
router.include_router(progress_router, prefix="/progress", tags=["LMS - Progress"])
router.include_router(certificates_router, prefix="/certificates", tags=["LMS - Certificates"])
router.include_router(badges_router, prefix="/badges", tags=["LMS - Badges"])
router.include_router(announcements_router, prefix="/announcements", tags=["LMS - Announcements"])
router.include_router(assignments_router, tags=["LMS - Assignments"])
router.include_router(assessments_router, tags=["LMS - Assessments"])
router.include_router(discussions_router, tags=["LMS - Discussions"])
router.include_router(bookmarks_router, prefix="/bookmarks", tags=["LMS - Bookmarks"])
router.include_router(transcripts_router, prefix="/transcripts", tags=["LMS - Transcripts"])
