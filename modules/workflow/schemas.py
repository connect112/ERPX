import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.workflow.models import ApprovalDecision, ApprovalRequestStatus


class WorkflowStepInput(BaseModel):
    step_order: int = Field(..., ge=1)
    approver_role_id: uuid.UUID
    name: str | None = None


class WorkflowCreateRequest(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    steps: list[WorkflowStepInput]


class WorkflowUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class WorkflowStepPublic(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    step_order: int
    approver_role_id: uuid.UUID
    name: str | None

    model_config = {"from_attributes": True}


class WorkflowPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    entity_type: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowDetailPublic(WorkflowPublic):
    steps: list[WorkflowStepPublic]


class WorkflowListResponse(BaseModel):
    items: list[WorkflowPublic]
    total: int


class ApprovalRequestSubmitRequest(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: uuid.UUID


class ApprovalActionRequest(BaseModel):
    comment: str | None = None


class ApprovalRequestPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workflow_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    current_step_order: int
    status: ApprovalRequestStatus
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalRequestListResponse(BaseModel):
    items: list[ApprovalRequestPublic]
    total: int


class ApprovalActionPublic(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    step_order: int
    actor_user_id: uuid.UUID
    decision: ApprovalDecision
    comment: str | None
    acted_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str
