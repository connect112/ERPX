import uuid
from datetime import date, datetime

from pydantic import BaseModel


class TabDef(BaseModel):
    key: str
    label: str


class CourseRef(BaseModel):
    id: uuid.UUID
    title: str
    course_type: str
    is_published: bool


class InternshipRef(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    can_view: bool
    can_manage: bool
    # instructors never delete: the screens hide delete actions when this is false
    can_delete: bool


class LearningContext(BaseModel):
    """What both Learning workspaces (the internship's and the course's) render from: the same seven tabs, and what the caller may do."""

    tabs: list[TabDef]
    course: CourseRef | None
    internships: list[InternshipRef]
    # true when the course has several internships the caller can reach: internship-owned data is then shown for one chosen at a time
    needs_selector: bool
    # course-level permissions by name (course-native data only; internship-owned data follows the internship's own flags above)
    course_caps: dict[str, bool]


class EnrollmentRow(BaseModel):
    selection_id: uuid.UUID
    student_id: uuid.UUID  # the internship student (what the grant and revoke endpoints take)
    lms_student_id: uuid.UUID | None  # their LMS student record, once access was granted (what recording a practical or viva result takes)
    name: str
    email: str
    stage_label: str
    lms_status: str
    lms_granted_at: datetime | None
    has_account: bool
    enrollment_id: uuid.UUID | None
    enrollment_status: str | None
    enrolled_on: date | None
    # "internship": this access created the enrolment; "independent": the student already had it (it is left alone on revoke); null: none
    provenance: str | None
    grant_blockers: list[str]
    progress_percent: float | None
    completed_lessons: int | None
    total_lessons: int | None


class IndependentEnrollment(BaseModel):
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    name: str
    status: str
    enrolled_on: date


class EnrollmentsView(BaseModel):
    internship_id: uuid.UUID
    course_id: uuid.UUID | None
    rows: list[EnrollmentRow]
    # other people enrolled in the course (not through this internship): only for staff who may see course enrolments; never managed here
    independent: list[IndependentEnrollment] | None = None


class ResultRow(BaseModel):
    """One student's standing in one activity, in that activity's own terms. There is no combined score: no weighting policy exists."""

    kind: str  # exam | assignment | assessment | project | practical | viva
    scope: str  # internship | course
    activity_id: uuid.UUID
    activity_title: str
    internship_id: uuid.UUID | None
    student_key: str  # selection id when known, else the LMS student id
    lms_student_id: uuid.UUID | None = None
    student_name: str
    student_email: str | None = None
    access_status: str | None  # granted | revoked for an internship's students
    state: str  # not_started | in_progress | submitted | graded
    completed: bool
    score: float | None
    total_marks: float | None
    percent: float | None
    passed: bool | None = None
    at: datetime | None


class ResultsView(BaseModel):
    internship_id: uuid.UUID | None
    course_id: uuid.UUID | None
    rows: list[ResultRow]
    # the kinds the caller may see, so a screen can say why one is missing
    included: list[str]
