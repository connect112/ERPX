import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.reports.models import ExportFormat
from modules.reports.registry import REPORT_CATALOG
from modules.reports.schemas import (
    MessageResponse,
    ReportDefinitionPublic,
    ReportExecutionPublic,
    RunReportJSONResponse,
    RunReportRequest,
    ScheduledReportCreateRequest,
    ScheduledReportPublic,
    ScheduledReportUpdateRequest,
)
from modules.reports.service import ReportService, ScheduledReportService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

_CONTENT_TYPES = {
    ExportFormat.CSV: "text/csv",
    ExportFormat.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ExportFormat.PDF: "application/pdf",
}
_EXTENSIONS = {ExportFormat.CSV: "csv", ExportFormat.EXCEL: "xlsx", ExportFormat.PDF: "pdf"}


@router.get("/catalog", response_model=list[ReportDefinitionPublic])
async def list_report_catalog(
    user: User = Depends(require_permissions("reports.run")),
):
    return [
        ReportDefinitionPublic(
            key=d.key, name=d.name, module=d.module, description=d.description, required_parameters=d.required_parameters
        )
        for d in REPORT_CATALOG
    ]


@router.post("/run")
async def run_report(
    payload: RunReportRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.run")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    execution, result, file_bytes = await service.run_report(
        organization_id,
        payload.report_key,
        payload.parameters,
        payload.export_format,
        executed_by_user_id=user.id,
    )

    if payload.export_format == ExportFormat.JSON:
        return RunReportJSONResponse(
            execution_id=execution.id, title=result.title, columns=result.columns, rows=result.rows, row_count=len(result.rows)
        )

    extension = _EXTENSIONS[payload.export_format]
    filename = f"{payload.report_key.replace('.', '_')}.{extension}"
    return Response(
        content=file_bytes,
        media_type=_CONTENT_TYPES[payload.export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/executions", response_model=dict)
async def list_executions(
    report_key: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.run")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    executions, total = await service.list_executions(organization_id, report_key=report_key, skip=skip, limit=limit)
    return {
        "items": [ReportExecutionPublic.model_validate(e) for e in executions],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/executions/{execution_id}", response_model=ReportExecutionPublic)
async def get_execution(
    execution_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.run")),
    db: AsyncSession = Depends(get_db),
):
    service = ReportService(db)
    execution = await service.get_execution(execution_id, organization_id)
    return ReportExecutionPublic.model_validate(execution)


# ---- Scheduled Reports ----


@router.post("/schedules", response_model=ScheduledReportPublic, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduledReportCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.schedule")),
    db: AsyncSession = Depends(get_db),
):
    service = ScheduledReportService(db)
    schedule = await service.create_schedule(organization_id, created_by_user_id=user.id, **payload.model_dump())
    return ScheduledReportPublic.model_validate(schedule)


@router.get("/schedules", response_model=dict)
async def list_schedules(
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.schedule")),
    db: AsyncSession = Depends(get_db),
):
    service = ScheduledReportService(db)
    schedules, total = await service.list_schedules(organization_id, is_active=is_active, skip=skip, limit=limit)
    return {
        "items": [ScheduledReportPublic.model_validate(s) for s in schedules],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/schedules/{schedule_id}", response_model=ScheduledReportPublic)
async def get_schedule(
    schedule_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.schedule")),
    db: AsyncSession = Depends(get_db),
):
    service = ScheduledReportService(db)
    schedule = await service.get_schedule(schedule_id, organization_id)
    return ScheduledReportPublic.model_validate(schedule)


@router.patch("/schedules/{schedule_id}", response_model=ScheduledReportPublic)
async def update_schedule(
    schedule_id: uuid.UUID,
    payload: ScheduledReportUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.schedule")),
    db: AsyncSession = Depends(get_db),
):
    service = ScheduledReportService(db)
    schedule = await service.update_schedule(schedule_id, organization_id, **payload.model_dump(exclude_unset=True))
    return ScheduledReportPublic.model_validate(schedule)


@router.post("/schedules/{schedule_id}/deactivate", response_model=ScheduledReportPublic)
async def deactivate_schedule(
    schedule_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("reports.schedule")),
    db: AsyncSession = Depends(get_db),
):
    service = ScheduledReportService(db)
    schedule = await service.deactivate_schedule(schedule_id, organization_id)
    return ScheduledReportPublic.model_validate(schedule)
