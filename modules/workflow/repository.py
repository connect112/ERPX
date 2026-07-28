import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.workflow.models import (
    ApprovalAction,
    ApprovalRequest,
    ApprovalRequestStatus,
    ApprovalStep,
    ApprovalWorkflow,
)


class ApprovalWorkflowRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ApprovalWorkflow:
        workflow = ApprovalWorkflow(**fields)
        self.db.add(workflow)
        await self.db.flush()
        await self.db.refresh(workflow)
        return workflow

    async def get_by_id(self, workflow_id: uuid.UUID, organization_id: uuid.UUID) -> ApprovalWorkflow | None:
        result = await self.db.execute(
            select(ApprovalWorkflow).where(
                ApprovalWorkflow.id == workflow_id, ApprovalWorkflow.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_active_for_entity_type(
        self, organization_id: uuid.UUID, entity_type: str
    ) -> ApprovalWorkflow | None:
        result = await self.db.execute(
            select(ApprovalWorkflow).where(
                ApprovalWorkflow.organization_id == organization_id,
                ApprovalWorkflow.entity_type == entity_type,
                ApprovalWorkflow.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def list_for_organization(
        self, organization_id: uuid.UUID, entity_type: str | None = None, skip: int = 0, limit: int = 50
    ) -> tuple[list[ApprovalWorkflow], int]:
        conditions = [ApprovalWorkflow.organization_id == organization_id]
        if entity_type is not None:
            conditions.append(ApprovalWorkflow.entity_type == entity_type)
        count_result = await self.db.execute(
            select(func.count()).select_from(ApprovalWorkflow).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(ApprovalWorkflow)
            .where(*conditions)
            .order_by(ApprovalWorkflow.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, workflow: ApprovalWorkflow, **fields) -> ApprovalWorkflow:
        for key, value in fields.items():
            if value is not None:
                setattr(workflow, key, value)
        await self.db.flush()
        await self.db.refresh(workflow)
        return workflow

    async def delete(self, workflow: ApprovalWorkflow) -> None:
        await self.db.delete(workflow)
        await self.db.flush()


class ApprovalStepRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ApprovalStep:
        step = ApprovalStep(**fields)
        self.db.add(step)
        await self.db.flush()
        await self.db.refresh(step)
        return step

    async def list_for_workflow(self, workflow_id: uuid.UUID) -> list[ApprovalStep]:
        result = await self.db.execute(
            select(ApprovalStep)
            .where(ApprovalStep.workflow_id == workflow_id)
            .order_by(ApprovalStep.step_order.asc())
        )
        return list(result.scalars().all())

    async def get_by_workflow_and_order(
        self, workflow_id: uuid.UUID, step_order: int
    ) -> ApprovalStep | None:
        result = await self.db.execute(
            select(ApprovalStep).where(
                ApprovalStep.workflow_id == workflow_id, ApprovalStep.step_order == step_order
            )
        )
        return result.scalar_one_or_none()

    async def delete_for_workflow(self, workflow_id: uuid.UUID) -> None:
        steps = await self.list_for_workflow(workflow_id)
        for step in steps:
            await self.db.delete(step)
        await self.db.flush()


class ApprovalRequestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ApprovalRequest:
        request = ApprovalRequest(**fields)
        self.db.add(request)
        await self.db.flush()
        await self.db.refresh(request)
        return request

    async def get_by_id(self, request_id: uuid.UUID, organization_id: uuid.UUID) -> ApprovalRequest | None:
        result = await self.db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.id == request_id, ApprovalRequest.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_pending_for_entity(
        self, entity_type: str, entity_id: uuid.UUID
    ) -> ApprovalRequest | None:
        result = await self.db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.entity_type == entity_type,
                ApprovalRequest.entity_id == entity_id,
                ApprovalRequest.status == ApprovalRequestStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[ApprovalRequest]:
        result = await self.db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.entity_type == entity_type, ApprovalRequest.entity_id == entity_id)
            .order_by(ApprovalRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: ApprovalRequestStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[ApprovalRequest], int]:
        conditions = [ApprovalRequest.organization_id == organization_id]
        if status is not None:
            conditions.append(ApprovalRequest.status == status)
        count_result = await self.db.execute(
            select(func.count()).select_from(ApprovalRequest).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(ApprovalRequest)
            .where(*conditions)
            .order_by(ApprovalRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_pending_for_roles(
        self, organization_id: uuid.UUID, role_ids: list[uuid.UUID]
    ) -> list[ApprovalRequest]:
        if not role_ids:
            return []
        result = await self.db.execute(
            select(ApprovalRequest)
            .join(
                ApprovalStep,
                (ApprovalStep.workflow_id == ApprovalRequest.workflow_id)
                & (ApprovalStep.step_order == ApprovalRequest.current_step_order),
            )
            .where(
                ApprovalRequest.organization_id == organization_id,
                ApprovalRequest.status == ApprovalRequestStatus.PENDING,
                ApprovalStep.approver_role_id.in_(role_ids),
            )
            .order_by(ApprovalRequest.created_at.asc())
        )
        return list(result.scalars().all())

    async def update(self, request: ApprovalRequest, **fields) -> ApprovalRequest:
        for key, value in fields.items():
            if value is not None:
                setattr(request, key, value)
        await self.db.flush()
        await self.db.refresh(request)
        return request


class ApprovalActionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> ApprovalAction:
        action = ApprovalAction(**fields)
        self.db.add(action)
        await self.db.flush()
        await self.db.refresh(action)
        return action

    async def list_for_request(self, request_id: uuid.UUID) -> list[ApprovalAction]:
        result = await self.db.execute(
            select(ApprovalAction)
            .where(ApprovalAction.request_id == request_id)
            .order_by(ApprovalAction.acted_at.asc())
        )
        return list(result.scalars().all())
