import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from modules.corporate.projects.models import ProjectStatus, ProjectType


class ProjectCreateRequest(BaseModel):
    client_id: uuid.UUID
    project_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    project_type: ProjectType = ProjectType.OTHER
    project_manager_employee_id: uuid.UUID | None = None
    start_date: date
    end_date: date | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    notes: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    project_manager_employee_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    notes: str | None = None


class ProjectStatusChangeRequest(BaseModel):
    status: ProjectStatus


class ProjectPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    client_id: uuid.UUID
    project_manager_employee_id: uuid.UUID | None
    project_code: str
    name: str
    description: str | None
    project_type: ProjectType
    status: ProjectStatus
    start_date: date
    end_date: date | None
    budget_amount: float | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
