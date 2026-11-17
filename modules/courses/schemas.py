import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from modules.courses.models import CourseLevel, CourseType

NO_COURSE_PRICE = "An internship course has no price of its own: its fee comes from the internship's onboarding settings."


class CourseCreateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    title: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255, pattern=r"^[a-z0-9-]+$")
    short_description: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    level: CourseLevel = CourseLevel.BEGINNER
    duration_hours: int | None = Field(default=None, ge=0)
    price: float = Field(default=0, ge=0)
    course_type: CourseType = CourseType.REGULAR
    # Internship courses only (hidden by default).
    show_internship_fee: bool = False

    @model_validator(mode="after")
    def _type_rules(self):
        if self.course_type == CourseType.INTERNSHIP and self.price:
            raise ValueError(NO_COURSE_PRICE)
        if self.course_type == CourseType.REGULAR and self.show_internship_fee:
            raise ValueError("Fee visibility applies to internship courses only.")
        return self


class CourseUpdateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=255)
    short_description: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    level: CourseLevel | None = None
    duration_hours: int | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    is_published: bool | None = None
    course_type: CourseType | None = None
    show_internship_fee: bool | None = None


class CoursePublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    category_id: uuid.UUID | None
    title: str
    slug: str
    short_description: str | None
    description: str | None
    thumbnail_url: str | None
    level: CourseLevel
    duration_hours: int | None
    price: float
    is_published: bool
    course_type: CourseType = CourseType.REGULAR
    show_internship_fee: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class LinkedInternship(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    # the fee of this internship, only when this is an internship course that shows it AND the caller may see finance AND the
    # internship has saved onboarding settings with a fee (never a default or an assumed amount)
    fee: dict | None = None


class CourseAdminOut(CoursePublic):
    """A course as staff see it: with the internships it is linked to (when the caller may see internships)."""

    linked_internships: list[LinkedInternship] = Field(default_factory=list)


class MessageResponse(BaseModel):
    message: str
