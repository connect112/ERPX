"""Analytics, experiments and reports.

Reading figures needs `social_media.view`; reading from Instagram now, and creating or changing experiments and reports, needs
`social_media.manage`. Nothing here posts, replies or changes anything on Instagram."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.social_media import metrics as M
from modules.social_media.analytics import AnalyticsService
from modules.social_media.connection import ConnectionService, computed_status
from modules.social_media.experiments import ExperimentService
from modules.social_media.inbox import parse_time
from modules.social_media.models import Report
from modules.social_media.reports import ReportService, last_period
from modules.social_media.schemas import ExperimentCreate, ExperimentDetail, ExperimentOut, ExperimentUpdate, ReportGenerate, ReportOut, SyncOut
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

VIEW = "social_media.view"
MANAGE = "social_media.manage"


def _catalogue() -> list[dict]:
    return [
        {"key": m.key, "label": m.label, "scope": m.scope, "kind": m.kind, "source": m.source, "period": m.period, "definition": m.definition, "limitation": m.limitation}
        for table in (M.ACCOUNT_METRICS, M.POST_METRICS)
        for m in table.values()
    ]


@router.get("/analytics/status")
async def analytics_status(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    account = await ConnectionService(db).get(organization_id)
    now = datetime.now(timezone.utc)
    connected = computed_status(account, now) in ("connected", "expiring")
    caps = (account.capabilities or {}) if account else {}
    state = ((account.sync_state or {}).get("analytics") or {}) if account else {}
    return {
        "connected": connected,
        "can_read": connected and caps.get("insights") != "unavailable",
        "insights_capability": caps.get("insights"),
        "last_sync_at": parse_time(state.get("last_at")),
        "stages": state.get("stages", {}),
        "unsupported_account_metrics": state.get("unsupported_account", []),
        "notes": [M.DATA_DELAY_NOTE, M.POOLED_NOTE, "A figure Instagram didn't give is shown as not available, never as zero."],
    }


@router.post("/analytics/sync", response_model=SyncOut)
async def sync_analytics(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Read the profile's figures and the recent posts' insights from Instagram now (at most every 15 minutes)."""
    result = await AnalyticsService(db).sync(organization_id)
    await db.commit()
    return SyncOut(**result)


@router.get("/analytics/overview")
async def analytics_overview(
    days: int = Query(default=28, ge=7, le=28),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    result = await service.overview(organization_id, days)
    result["consistency"] = await service.consistency(organization_id, result["period"]["start"], result["period"]["end"])
    return result


@router.get("/analytics/posts")
async def analytics_posts(
    limit: int = Query(default=40, ge=1, le=100),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    rows = await service.posts(organization_id, limit)
    return {
        "items": rows,
        "breakdowns": {key: service.breakdown(rows, key) for key in ("kind", "pillar", "hook", "cta", "time_of_day")},
        "pooled_note": M.POOLED_NOTE,
        "note": "Only the 25 most recent posts are read from Instagram. Stories aren't tracked because Instagram only keeps their figures for 24 hours.",
    }


@router.get("/analytics/metrics")
async def analytics_metrics(user: User = Depends(require_permissions(VIEW))):
    """What every metric means, where it comes from and what limits it."""
    return {"metrics": _catalogue(), "pooled_note": M.POOLED_NOTE}


# ---------------- experiments ----------------


@router.get("/experiments", response_model=list[ExperimentOut])
async def list_experiments(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    return await ExperimentService(db).everything(organization_id)


@router.post("/experiments", response_model=ExperimentOut, status_code=201)
async def create_experiment(
    payload: ExperimentCreate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    row = await ExperimentService(db).create(organization_id, user.id, payload.model_dump())
    result = ExperimentOut.model_validate(row)
    await db.commit()
    return result


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetail)
async def get_experiment(
    experiment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    service = ExperimentService(db)
    row = await service.get(organization_id, experiment_id)
    return ExperimentDetail(experiment=ExperimentOut.model_validate(row), results=await service.results(organization_id, row))


@router.patch("/experiments/{experiment_id}", response_model=ExperimentOut)
async def update_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentUpdate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    row = await ExperimentService(db).update(organization_id, experiment_id, payload.model_dump(exclude_unset=True))
    result = ExperimentOut.model_validate(row)
    await db.commit()
    return result


@router.delete("/experiments/{experiment_id}", status_code=204)
async def delete_experiment(
    experiment_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await ExperimentService(db).delete(organization_id, experiment_id)
    await db.commit()


# ---------------- reports ----------------


async def _report_out(db: AsyncSession, row: Report) -> ReportOut:
    name = None
    if row.generated_by_user_id:
        name = (await db.execute(select(User.full_name).where(User.id == row.generated_by_user_id))).scalar_one_or_none()
    return ReportOut(
        id=row.id, kind=row.kind, period_start=row.period_start, period_end=row.period_end, generated_at=row.updated_at, generated_by=name,
        automatic=row.generated_by_user_id is None, data=row.data,
    )


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    kind: str | None = Query(default=None, pattern=r"^(weekly|monthly)$"),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    return [await _report_out(db, r) for r in await ReportService(db).recent(organization_id, kind)]


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(VIEW)),
    db: AsyncSession = Depends(get_db),
):
    return await _report_out(db, await ReportService(db).get(organization_id, report_id))


@router.post("/reports", response_model=ReportOut)
async def generate_report(
    payload: ReportGenerate,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions(MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Build (or rebuild) the report for a finished period from the figures ERPX holds."""
    start = payload.period_start or last_period(payload.kind, datetime.now(timezone.utc).date())[0]
    row = await ReportService(db).generate(organization_id, payload.kind, start, user.id)
    result = await _report_out(db, row)
    await db.commit()
    return result
