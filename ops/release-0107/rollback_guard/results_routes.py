"""
ERPX release 0107 -- ROLLBACK GUARD for the course-results endpoint.

THIS FILE IS NEVER PART OF THE APPLICATION. 90_rollback_code_only.sh bakes it into a derived copy of the PREVIOUS api image, in place of
modules/examinations/results/routes.py, and only after checking that the file it replaces is byte-for-byte the previous release's (sha256 below).

WHY. In the previous release this route needs only the permission ``examinations.results.view``, which every Student holds, and it never asks whose
results are requested. Any logged-in student could therefore read any other student's marks (exam, practical, viva) with
    GET /api/v1/examinations/results/{student_id}/course/{course_id}
Release 0107 closes that (modules/students/actor.py: ensure_own_or_staff). A code-only rollback would bring the hole back, so the previous image is
not restored as it was: it gets this guard.

THE RULE (the same as release 0107): the caller must be
  * the student the results are for (their own student record), or
  * a platform superuser, or
  * staff: holding at least one of STAFF's permissions (grading, or managing exams / practicals / viva).
Anyone else gets 403. The caller's organization is still enforced by the service, as before. Nothing here widens access, and the guard fails closed:
if the student record or the permissions cannot be read, the request errors out and no result is returned.

It uses only what the previous image already has (StudentRepository.get_by_user_id, AuthorizationRepository.get_permission_codes_for_user,
AuthorizationError), so it runs unchanged on the previous code.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.authorization.repository import AuthorizationRepository
from modules.examinations.results.schemas import StudentCourseResultResponse
from modules.examinations.results.service import ResultsService
from modules.students.repository import StudentRepository
from modules.users.dependencies import get_current_user_organization_id

ROLLBACK_GUARD = "results-0107"
# sha256 of the previous release's modules/examinations/results/routes.py (the only version that has ever existed): 90_rollback_code_only.sh
# refuses to build the guard image over any other file, because then it could not promise that this file is a safe replacement.
REPLACES_SHA256 = "4a889744d91d824382172a1641cfb1194fcec52a6b045ea59e75c918bd3360c3"

router = APIRouter()

STAFF = {"examinations.evaluation.grade", "examinations.exams.manage", "examinations.practicals.manage", "examinations.viva.manage"}
NOT_YOURS = "You can only view your own results."


async def _ensure_own_or_staff(db: AsyncSession, user: User, student_id: uuid.UUID) -> None:
    if user.is_superuser:
        return
    own = await StudentRepository(db).get_by_user_id(user.id)
    if own is not None and own.id == student_id:
        return
    codes = await AuthorizationRepository(db).get_permission_codes_for_user(user.id)
    if STAFF & set(codes):
        return
    raise AuthorizationError(NOT_YOURS)


@router.get("/{student_id}/course/{course_id}", response_model=StudentCourseResultResponse)
async def get_student_course_result(
    student_id: uuid.UUID,
    course_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("examinations.results.view")),
    db: AsyncSession = Depends(get_db),
):
    await _ensure_own_or_staff(db, user, student_id)
    service = ResultsService(db)
    return await service.get_student_course_result(student_id, course_id, organization_id)
