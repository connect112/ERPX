import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authorization.repository import AuthorizationRepository
from modules.workflow.models import (
    ApprovalAction,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalRequestStatus,
    ApprovalStep,
    ApprovalWorkflow,
)
from modules.workflow.repository import (
    ApprovalActionRepository,
    ApprovalRequestRepository,
    ApprovalStepRepository,
    ApprovalWorkflowRepository,
)

logger = get_logger(__name__)


class ApprovalWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ApprovalWorkflowRepository(db)
        self.step_repo = ApprovalStepRepository(db)

    async def create_workflow(
        self,
        organization_id: uuid.UUID,
        entity_type: str,
        name: str,
        description: str | None,
        steps: list[dict],
    ) -> ApprovalWorkflow:
        if not steps:
            raise ValidationError("A workflow needs at least one approval step.")

        workflow = await self.repo.create(
            organization_id=organization_id,
            entity_type=entity_type,
            name=name,
            description=description,
        )
        for step in sorted(steps, key=lambda s: s["step_order"]):
            await self.step_repo.create(
                workflow_id=workflow.id,
                step_order=step["step_order"],
                approver_role_id=step["approver_role_id"],
                name=step.get("name"),
            )
        logger.info("approval_workflow_created", workflow_id=str(workflow.id), steps=len(steps))
        return workflow

    async def get_workflow(self, workflow_id: uuid.UUID, organization_id: uuid.UUID) -> ApprovalWorkflow:
        workflow = await self.repo.get_by_id(workflow_id, organization_id)
        if not workflow:
            raise NotFoundError("Approval workflow", workflow_id)
        return workflow

    async def get_steps(self, workflow_id: uuid.UUID) -> list[ApprovalStep]:
        return await self.step_repo.list_for_workflow(workflow_id)

    async def list_workflows(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_workflow(
        self, workflow_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> ApprovalWorkflow:
        workflow = await self.get_workflow(workflow_id, organization_id)
        updated = await self.repo.update(workflow, **fields)
        logger.info("approval_workflow_updated", workflow_id=str(workflow_id))
        return updated

    async def delete_workflow(self, workflow_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        workflow = await self.get_workflow(workflow_id, organization_id)
        await self.step_repo.delete_for_workflow(workflow_id)
        await self.repo.delete(workflow)
        logger.info("approval_workflow_deleted", workflow_id=str(workflow_id))


class ApprovalRequestService:
    """
    The reusable engine other modules call into: `submit_request` at
    creation time, `approve`/`reject` from whatever "my approvals" UI a
    caller builds. Every check here is generic (role membership, step
    ordering) — no module-specific knowledge lives in this class.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow_repo = ApprovalWorkflowRepository(db)
        self.step_repo = ApprovalStepRepository(db)
        self.request_repo = ApprovalRequestRepository(db)
        self.action_repo = ApprovalActionRepository(db)
        self.authz_repo = AuthorizationRepository(db)

    async def submit_request(
        self,
        organization_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        requested_by_user_id: uuid.UUID,
    ) -> ApprovalRequest:
        workflow = await self.workflow_repo.get_active_for_entity_type(organization_id, entity_type)
        if not workflow:
            raise ValidationError(f"No active approval workflow configured for '{entity_type}'.")

        existing = await self.request_repo.get_pending_for_entity(entity_type, entity_id)
        if existing:
            raise ConflictError("An approval request is already pending for this record.")

        request = await self.request_repo.create(
            organization_id=organization_id,
            workflow_id=workflow.id,
            entity_type=entity_type,
            entity_id=entity_id,
            requested_by_user_id=requested_by_user_id,
            current_step_order=1,
            status=ApprovalRequestStatus.PENDING,
        )
        logger.info("approval_request_submitted", request_id=str(request.id), entity_type=entity_type)
        return request

    async def get_request(self, request_id: uuid.UUID, organization_id: uuid.UUID) -> ApprovalRequest:
        request = await self.request_repo.get_by_id(request_id, organization_id)
        if not request:
            raise NotFoundError("Approval request", request_id)
        return request

    async def list_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[ApprovalRequest]:
        return await self.request_repo.list_for_entity(entity_type, entity_id)

    async def list_requests(self, organization_id: uuid.UUID, **filters):
        return await self.request_repo.list_for_organization(organization_id, **filters)

    async def list_actions(self, request_id: uuid.UUID) -> list[ApprovalAction]:
        return await self.action_repo.list_for_request(request_id)

    async def list_pending_for_user(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ApprovalRequest]:
        roles = await self.authz_repo.get_roles_for_user(user_id)
        role_ids = [r.id for r in roles]
        return await self.request_repo.list_pending_for_roles(organization_id, role_ids)

    async def _current_step(self, request: ApprovalRequest) -> ApprovalStep:
        step = await self.step_repo.get_by_workflow_and_order(request.workflow_id, request.current_step_order)
        if not step:
            raise NotFoundError("Approval step", request.current_step_order)
        return step

    async def _assert_can_act(self, request: ApprovalRequest, actor_user_id: uuid.UUID) -> ApprovalStep:
        if request.status != ApprovalRequestStatus.PENDING:
            raise ValidationError("This approval request has already been resolved.")
        step = await self._current_step(request)
        roles = await self.authz_repo.get_roles_for_user(actor_user_id)
        role_ids = {r.id for r in roles}
        if step.approver_role_id not in role_ids:
            raise AuthorizationError("You are not an approver for the current step of this request.")
        return step

    async def approve(
        self,
        request_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        comment: str | None = None,
    ) -> ApprovalRequest:
        request = await self.get_request(request_id, organization_id)
        step = await self._assert_can_act(request, actor_user_id)

        await self.action_repo.create(
            request_id=request.id,
            step_order=step.step_order,
            actor_user_id=actor_user_id,
            decision=ApprovalDecision.APPROVED,
            comment=comment,
            acted_at=datetime.now(timezone.utc),
        )

        steps = await self.step_repo.list_for_workflow(request.workflow_id)
        is_last_step = step.step_order >= max(s.step_order for s in steps)

        if is_last_step:
            updated = await self.request_repo.update(
                request,
                status=ApprovalRequestStatus.APPROVED,
                resolved_at=datetime.now(timezone.utc),
            )
            logger.info("approval_request_approved", request_id=str(request_id))
        else:
            next_order = min(s.step_order for s in steps if s.step_order > step.step_order)
            request.current_step_order = next_order
            await self.db.flush()
            await self.db.refresh(request)
            updated = request
            logger.info(
                "approval_request_step_advanced", request_id=str(request_id), next_step=next_order
            )
        return updated

    async def reject(
        self,
        request_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        comment: str | None = None,
    ) -> ApprovalRequest:
        request = await self.get_request(request_id, organization_id)
        step = await self._assert_can_act(request, actor_user_id)

        await self.action_repo.create(
            request_id=request.id,
            step_order=step.step_order,
            actor_user_id=actor_user_id,
            decision=ApprovalDecision.REJECTED,
            comment=comment,
            acted_at=datetime.now(timezone.utc),
        )
        updated = await self.request_repo.update(
            request, status=ApprovalRequestStatus.REJECTED, resolved_at=datetime.now(timezone.utc)
        )
        logger.info("approval_request_rejected", request_id=str(request_id))
        return updated

    async def cancel(
        self, request_id: uuid.UUID, organization_id: uuid.UUID, requester_user_id: uuid.UUID
    ) -> ApprovalRequest:
        request = await self.get_request(request_id, organization_id)
        if request.requested_by_user_id != requester_user_id:
            raise AuthorizationError("Only the original requester can cancel this request.")
        if request.status != ApprovalRequestStatus.PENDING:
            raise ValidationError("This approval request has already been resolved.")
        updated = await self.request_repo.update(
            request, status=ApprovalRequestStatus.CANCELLED, resolved_at=datetime.now(timezone.utc)
        )
        logger.info("approval_request_cancelled", request_id=str(request_id))
        return updated
