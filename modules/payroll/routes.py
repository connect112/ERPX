import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.payroll.models import PayrollRunStatus
from modules.payroll.schemas import (
    MessageResponse,
    PayrollRunFinalizeRequest,
    PayrollRunGenerateRequest,
    PayrollRunGenerationResult,
    PayrollRunMarkPaidRequest,
    PayrollRunPublic,
    PayslipPublic,
    SalaryComponentCreateRequest,
    SalaryComponentPublic,
    SalaryComponentUpdateRequest,
    SalaryStructureCreateRequest,
    SalaryStructurePublic,
)
from modules.payroll.service import PayrollService, SalaryComponentService, SalaryStructureService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Salary Components ----


@router.post("/components", response_model=SalaryComponentPublic, status_code=status.HTTP_201_CREATED)
async def create_salary_component(
    payload: SalaryComponentCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.components.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SalaryComponentService(db)
    component = await service.create_component(organization_id, **payload.model_dump())
    return SalaryComponentPublic.model_validate(component)


@router.get("/components", response_model=list[SalaryComponentPublic])
async def list_salary_components(
    is_active: bool | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.components.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SalaryComponentService(db)
    components = await service.list_components(organization_id, is_active)
    return [SalaryComponentPublic.model_validate(c) for c in components]


@router.patch("/components/{component_id}", response_model=SalaryComponentPublic)
async def update_salary_component(
    component_id: uuid.UUID,
    payload: SalaryComponentUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.components.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SalaryComponentService(db)
    component = await service.update_component(
        component_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return SalaryComponentPublic.model_validate(component)


# ---- Salary Structures ----


@router.post("/structures", response_model=SalaryStructurePublic, status_code=status.HTTP_201_CREATED)
async def create_salary_structure(
    payload: SalaryStructureCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.structures.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = SalaryStructureService(db)
    data = payload.model_dump()
    lines = data.pop("lines")
    structure = await service.create_structure(organization_id, lines=lines, **data)
    return SalaryStructurePublic.model_validate(structure)


@router.get("/structures/{structure_id}", response_model=SalaryStructurePublic)
async def get_salary_structure(
    structure_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.structures.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SalaryStructureService(db)
    structure = await service.get_structure(structure_id, organization_id)
    return SalaryStructurePublic.model_validate(structure)


@router.get("/structures/employees/{employee_id}", response_model=list[SalaryStructurePublic])
async def list_employee_structures(
    employee_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.structures.view")),
    db: AsyncSession = Depends(get_db),
):
    service = SalaryStructureService(db)
    structures = await service.list_for_employee(employee_id, organization_id)
    return [SalaryStructurePublic.model_validate(s) for s in structures]


# ---- Payroll Runs ----


@router.post("/runs", response_model=PayrollRunGenerationResult, status_code=status.HTTP_201_CREATED)
async def generate_payroll_run(
    payload: PayrollRunGenerateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    run, processed, skipped = await service.generate_run(
        organization_id, created_by_user_id=user.id, **payload.model_dump()
    )
    return PayrollRunGenerationResult(
        run=PayrollRunPublic.model_validate(run),
        employees_processed=processed,
        employees_skipped_no_structure=skipped,
    )


@router.get("/runs", response_model=dict)
async def list_payroll_runs(
    status_filter: PayrollRunStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    runs, total = await service.list_runs(organization_id, status=status_filter, skip=skip, limit=limit)
    return {
        "items": [PayrollRunPublic.model_validate(r) for r in runs],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/runs/{run_id}", response_model=PayrollRunPublic)
async def get_payroll_run(
    run_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    run = await service.get_run(run_id, organization_id)
    return PayrollRunPublic.model_validate(run)


@router.get("/runs/{run_id}/payslips", response_model=list[PayslipPublic])
async def list_run_payslips(
    run_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    payslips = await service.list_payslips(run_id, organization_id)
    return [PayslipPublic.model_validate(p) for p in payslips]


@router.post("/runs/{run_id}/finalize", response_model=PayrollRunPublic)
async def finalize_payroll_run(
    run_id: uuid.UUID,
    payload: PayrollRunFinalizeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.finalize")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    run = await service.finalize_run(
        run_id, organization_id, payload.net_payable_account_id, created_by_user_id=user.id
    )
    return PayrollRunPublic.model_validate(run)


@router.post("/runs/{run_id}/mark-paid", response_model=PayrollRunPublic)
async def mark_payroll_run_paid(
    run_id: uuid.UUID,
    payload: PayrollRunMarkPaidRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.finalize")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    run = await service.mark_paid(run_id, organization_id, payload.bank_account_id, payload.payment_date)
    return PayrollRunPublic.model_validate(run)


@router.post("/runs/{run_id}/cancel", response_model=PayrollRunPublic)
async def cancel_payroll_run(
    run_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    run = await service.cancel_run(run_id, organization_id)
    return PayrollRunPublic.model_validate(run)


# ---- Payslips ----


@router.get("/payslips/{payslip_id}", response_model=PayslipPublic)
async def get_payslip(
    payslip_id: uuid.UUID,
    user: User = Depends(require_permissions("payroll.runs.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    payslip = await service.get_payslip(payslip_id)
    return PayslipPublic.model_validate(payslip)


@router.get("/payslips/employees/{employee_id}", response_model=dict)
async def list_employee_payslips(
    employee_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("payroll.runs.view")),
    db: AsyncSession = Depends(get_db),
):
    service = PayrollService(db)
    payslips, total = await service.list_payslips_for_employee(
        employee_id, organization_id, skip=skip, limit=limit
    )
    return {
        "items": [PayslipPublic.model_validate(p) for p in payslips],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
