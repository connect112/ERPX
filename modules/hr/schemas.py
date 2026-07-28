import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DepartmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    parent_department_id: uuid.UUID | None = None
    head_employee_id: uuid.UUID | None = None
    description: str | None = None


class DepartmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    parent_department_id: uuid.UUID | None = None
    head_employee_id: uuid.UUID | None = None
    description: str | None = None
    is_active: bool | None = None


class DepartmentPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    parent_department_id: uuid.UUID | None
    head_employee_id: uuid.UUID | None
    name: str
    code: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DesignationCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    grade_level: int | None = Field(default=None, ge=1)
    description: str | None = None


class DesignationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=150)
    grade_level: int | None = Field(default=None, ge=1)
    description: str | None = None
    is_active: bool | None = None


class DesignationPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    code: str
    grade_level: int | None
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
