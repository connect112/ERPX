import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.integrations.models import Integration, IntegrationTestStatus
from modules.integrations.repository import IntegrationRepository

logger = get_logger(__name__)

TEST_TIMEOUT_SECONDS = 5.0


class IntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = IntegrationRepository(db)

    async def create_integration(
        self, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, **fields
    ) -> Integration:
        integration = await self.repo.create(
            organization_id=organization_id, created_by_user_id=created_by_user_id, **fields
        )
        logger.info("integration_created", integration_id=str(integration.id), provider=integration.provider)
        return integration

    async def get_integration(self, integration_id: uuid.UUID, organization_id: uuid.UUID) -> Integration:
        integration = await self.repo.get_by_id(integration_id, organization_id)
        if not integration:
            raise NotFoundError("Integration", integration_id)
        return integration

    async def list_integrations(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_integration(
        self, integration_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> Integration:
        integration = await self.get_integration(integration_id, organization_id)
        updated = await self.repo.update(integration, **fields)
        logger.info("integration_updated", integration_id=str(integration_id))
        return updated

    async def delete_integration(self, integration_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        integration = await self.get_integration(integration_id, organization_id)
        await self.repo.delete(integration)
        logger.info("integration_deleted", integration_id=str(integration_id))

    async def test_connection(self, integration_id: uuid.UUID, organization_id: uuid.UUID) -> Integration:
        """A real outbound HTTP request to `base_url` — no OAuth handshake
        (we hold no real Zoom/Slack/etc. credentials in this codebase), but
        a genuine reachability check: whatever the endpoint actually
        returns is what gets recorded, not a hardcoded success."""
        integration = await self.get_integration(integration_id, organization_id)

        headers = {}
        if integration.api_key:
            headers["Authorization"] = f"Bearer {integration.api_key}"

        try:
            async with httpx.AsyncClient(timeout=TEST_TIMEOUT_SECONDS) as client:
                response = await client.get(integration.base_url, headers=headers)
            status = IntegrationTestStatus.SUCCESS if response.status_code < 500 else IntegrationTestStatus.FAILED
            message = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            status = IntegrationTestStatus.FAILED
            message = f"{type(exc).__name__}: {exc}"[:500]

        integration.last_tested_at = datetime.now(timezone.utc)
        integration.last_test_status = status
        integration.last_test_message = message
        await self.db.flush()
        await self.db.refresh(integration)
        logger.info(
            "integration_tested", integration_id=str(integration_id), status=status.value, message=message
        )
        return integration
