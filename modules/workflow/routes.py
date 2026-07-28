import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.workflow.models import ApprovalRequestStatus
from modules.workflow.schemas import (
    ApprovalActionPublic,
    ApprovalActionRequest,
    ApprovalRequestListResponse,
    ApprovalRequestPublic,
    ApprovalRequestSubmitRequest,
    MessageResponse,
    WorkflowCreateRequest,
    WorkflowDetailPublic,
    WorkflowListResponse,
    WorkflowPublic,
    WorkflowStepPublic,
    WorkflowUpdateRequest,
)
from modules.workflow.service import ApprovalRequestService, ApprovalWorkflowService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Staff: workflow configuration ----


@router.post("/workflows", response_model=WorkflowDetailPublic, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalWorkflowService(db)
    workflow = await service.create_workflow(
        organization_id,
        entity_type=payload.entity_type,
        name=payload.name,
        description=payload.description,
        steps=[s.model_dump() for s in payload.steps],
    )
    steps = await service.get_steps(workflow.id)
    return WorkflowDetailPublic(
        **WorkflowPublic.model_validate(workflow).model_dump(),
        steps=[WorkflowStepPublic.model_validate(s) for s in steps],
    )


@router.get("/workflows", response_model=WorkflowListResponse)
async def list_workflows(
    entity_type: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalWorkflowService(db)
    workflows, total = await service.list_workflows(
        organization_id, entity_type=entity_type, skip=skip, limit=limit
    )
    return WorkflowListResponse(items=[WorkflowPublic.model_validate(w) for w in workflows], total=total)


@router.get("/workflows/{workflow_id}", response_model=WorkflowDetailPublic)
async def get_workflow(
    workflow_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalWorkflowService(db)
    workflow = await service.get_workflow(workflow_id, organization_id)
    steps = await service.get_steps(workflow_id)
    return WorkflowDetailPublic(
        **WorkflowPublic.model_validate(workflow).model_dump(),
        steps=[WorkflowStepPublic.model_validate(s) for s in steps],
    )


@router.patch("/workflows/{workflow_id}", response_model=WorkflowPublic)
async def update_workflow(
    workflow_id: uuid.UUID,
    payload: WorkflowUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalWorkflowService(db)
    workflow = await service.update_workflow(
        workflow_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return WorkflowPublic.model_validate(workflow)


@router.delete("/workflows/{workflow_id}", response_model=MessageResponse)
async def delete_workflow(
    workflow_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalWorkflowService(db)
    await service.delete_workflow(workflow_id, organization_id)
    return MessageResponse(message="Approval workflow deleted successfully.")


# ---- Approval requests: any authenticated user ----


@router.post("/requests", response_model=ApprovalRequestPublic, status_code=status.HTTP_201_CREATED)
async def submit_request(
    payload: ApprovalRequestSubmitRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    request = await service.submit_request(
        organization_id, payload.entity_type, payload.entity_id, user.id
    )
    return ApprovalRequestPublic.model_validate(request)


@router.get("/requests/me", response_model=list[ApprovalRequestPublic])
async def list_my_requests(
    entity_type: str = Query(...),
    entity_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    requests = await service.list_for_entity(entity_type, entity_id)
    return [ApprovalRequestPublic.model_validate(r) for r in requests]


@router.get("/requests/me/pending-approvals", response_model=list[ApprovalRequestPublic])
async def list_my_pending_approvals(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    requests = await service.list_pending_for_user(organization_id, user.id)
    return [ApprovalRequestPublic.model_validate(r) for r in requests]


@router.post("/requests/{request_id}/approve", response_model=ApprovalRequestPublic)
async def approve_request(
    request_id: uuid.UUID,
    payload: ApprovalActionRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    request = await service.approve(request_id, organization_id, user.id, payload.comment)
    return ApprovalRequestPublic.model_validate(request)


@router.post("/requests/{request_id}/reject", response_model=ApprovalRequestPublic)
async def reject_request(
    request_id: uuid.UUID,
    payload: ApprovalActionRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    request = await service.reject(request_id, organization_id, user.id, payload.comment)
    return ApprovalRequestPublic.model_validate(request)


@router.post("/requests/{request_id}/cancel", response_model=ApprovalRequestPublic)
async def cancel_request(
    request_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    request = await service.cancel(request_id, organization_id, user.id)
    return ApprovalRequestPublic.model_validate(request)


@router.get("/requests/{request_id}/actions", response_model=list[ApprovalActionPublic])
async def list_request_actions(
    request_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    await service.get_request(request_id, organization_id)
    actions = await service.list_actions(request_id)
    return [ApprovalActionPublic.model_validate(a) for a in actions]


# ---- Staff: oversight ----


@router.get("/requests", response_model=ApprovalRequestListResponse)
async def list_all_requests(
    status_filter: ApprovalRequestStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    requests, total = await service.list_requests(
        organization_id, status=status_filter, skip=skip, limit=limit
    )
    return ApprovalRequestListResponse(
        items=[ApprovalRequestPublic.model_validate(r) for r in requests], total=total
    )


@router.get("/requests/{request_id}", response_model=ApprovalRequestPublic)
async def get_request(
    request_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workflow.view")),
    db: AsyncSession = Depends(get_db),
):
    service = ApprovalRequestService(db)
    request = await service.get_request(request_id, organization_id)
    return ApprovalRequestPublic.model_validate(request)
