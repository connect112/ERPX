import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.settings.schemas import SettingPublic, SettingUpsertRequest
from modules.settings.service import SettingsService

router = APIRouter()


@router.get("/{organization_id}", response_model=list[SettingPublic])
async def list_settings(
    organization_id: uuid.UUID,
    user: User = Depends(require_permissions("settings.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SettingsService(db)
    settings = await service.list_settings(organization_id)
    return [SettingPublic.model_validate(s) for s in settings]


@router.put("/{organization_id}", response_model=SettingPublic)
async def upsert_setting(
    organization_id: uuid.UUID,
    payload: SettingUpsertRequest,
    user: User = Depends(require_permissions("settings.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SettingsService(db)
    setting = await service.upsert_setting(organization_id, payload.key, payload.value)
    return SettingPublic.model_validate(setting)
