import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.integrations.models import Integration, IntegrationTestStatus


class IntegrationCreateRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=2, max_length=255)
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    config: str | None = None
    is_enabled: bool = True


class IntegrationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    config: str | None = None
    is_enabled: bool | None = None


def _mask(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 4:
        return "****"
    return f"****{api_key[-4:]}"


class IntegrationPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    provider: str
    name: str
    base_url: str
    masked_api_key: str | None
    config: str | None
    is_enabled: bool
    last_tested_at: datetime | None
    last_test_status: IntegrationTestStatus | None
    last_test_message: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, integration: Integration) -> "IntegrationPublic":
        return cls(
            id=integration.id,
            organization_id=integration.organization_id,
            created_by_user_id=integration.created_by_user_id,
            provider=integration.provider,
            name=integration.name,
            base_url=integration.base_url,
            masked_api_key=_mask(integration.api_key),
            config=integration.config,
            is_enabled=integration.is_enabled,
            last_tested_at=integration.last_tested_at,
            last_test_status=integration.last_test_status,
            last_test_message=integration.last_test_message,
            created_at=integration.created_at,
        )


class IntegrationListResponse(BaseModel):
    items: list[IntegrationPublic]
    total: int


class MessageResponse(BaseModel):
    message: str
