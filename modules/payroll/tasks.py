"""
Payroll module — background tasks.

Auto-generates each organization's monthly payroll draft on the last
working day of the month. What happens next depends on whether that org
has configured both Organization.default_salary_payable_account_id and
default_expense_reimbursement_component_id (see modules/hr/routes.py's
GET/PATCH /hr/settings):

- Neither configured (the default): notify that org's Administrator(s)
  in-app and by email that a draft is ready for their review, exactly
  as before this pipeline existed. Nothing is finalized or paid
  automatically.
- Both configured: also sweep in every employee's expense claims
  approved for this exact period (not yet applied to any run), finalize
  the run (posting the real journal entry), and email every employee
  their own payslip PDF -- fully hands-off. Admins still get a
  notification, just informational rather than "please review."
  Marking the run paid once money actually moves is still a manual,
  separate step either way -- this pipeline never does that.
"""

import uuid
from datetime import date

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.authorization.repository import AuthorizationRepository
from modules.employees.repository import EmployeeRepository
from modules.notifications.models import NotificationType
from modules.notifications.service import NotificationService
from modules.organizations.repository import OrganizationRepository
from modules.organizations.service import SYSTEM_ORG_SLUG
from modules.payroll.service import PayrollService
from packages.email.service import EmailAttachment, email_service
from packages.email.templates import payroll_draft_ready_email, payslip_ready_email

logger = get_logger(__name__)

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


async def _auto_generate_for_all_organizations(today: date | None = None) -> int:
    """`today` is injectable so tests don't depend on actually running on
    the last working day of the month -- mirrors
    PayrollService.auto_generate_monthly_draft's own same-purpose param."""
    generated = 0
    async with get_db_context() as db:
        org_repo = OrganizationRepository(db)
        organizations = await org_repo.list_all(skip=0, limit=10_000, exclude_slug=SYSTEM_ORG_SLUG)
        payroll_service = PayrollService(db)
        authz_repo = AuthorizationRepository(db)
        notification_service = NotificationService(db)

        for org in organizations:
            if not org.is_active:
                continue
            run = await payroll_service.auto_generate_monthly_draft(org.id, today=today)
            if run is None:
                continue
            generated += 1
            period_label = f"{_MONTH_NAMES[run.period_month - 1]} {run.period_year}"

            finalized = False
            if org.default_expense_reimbursement_component_id:
                await payroll_service.apply_approved_expense_claims_to_run(run, org.id)
                run = await payroll_service.get_run(run.id, org.id)

            if org.default_salary_payable_account_id:
                try:
                    run = await payroll_service.finalize_run(run.id, org.id, org.default_salary_payable_account_id)
                    finalized = True
                except Exception:
                    logger.exception(
                        "payroll_auto_finalize_failed", organization_id=str(org.id), run_id=str(run.id)
                    )

            admins = await authz_repo.list_users_with_role_in_organization(org.id, "administrator")
            if finalized:
                for admin in admins:
                    await notification_service.create_notification(
                        organization_id=org.id,
                        user_id=admin.id,
                        title=f"Payroll finalized: {period_label}",
                        body=(
                            f"The {period_label} payroll run has been generated, finalized, and "
                            f"emailed to every employee automatically."
                        ),
                        notification_type=NotificationType.SUCCESS,
                        link_url=f"/payroll/runs/{run.id}",
                        source="payroll_auto_finalize",
                    )

                payslips = await payroll_service.list_payslips(run.id, org.id)
                for payslip in payslips:
                    send_payslip_email_task.delay(str(payslip.id), str(org.id), period_label)
            else:
                review_url = f"{settings.FRONTEND_URL}/payroll/runs/{run.id}"
                for admin in admins:
                    await notification_service.create_notification(
                        organization_id=org.id,
                        user_id=admin.id,
                        title=f"Payroll draft ready: {period_label}",
                        body=f"The {period_label} payroll draft has been generated and is ready for your review.",
                        notification_type=NotificationType.ACTION_REQUIRED,
                        link_url=f"/payroll/runs/{run.id}",
                        source="payroll_auto_draft",
                    )
                    send_payroll_draft_ready_email_task.delay(admin.email, admin.full_name, period_label, review_url)

            logger.info(
                "payroll_draft_auto_generated",
                organization_id=str(org.id),
                run_id=str(run.id),
                admins_notified=len(admins),
                auto_finalized=finalized,
            )
    return generated


@celery_app.task(
    name="payroll.auto_generate_monthly_drafts",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def auto_generate_monthly_drafts_task() -> None:
    count = run_async(_auto_generate_for_all_organizations())
    logger.info("payroll_auto_generate_run_complete", organizations_generated=count)


@celery_app.task(name="payroll.send_draft_ready_email", bind=True, max_retries=3)
def send_payroll_draft_ready_email_task(
    self, to_email: str, full_name: str, period_label: str, review_url: str
) -> None:
    subject, text, html = payroll_draft_ready_email(full_name, period_label, review_url)
    success = run_async(email_service.send(to_email, subject, text, html))
    if not success:
        logger.warning("payroll_draft_ready_email_retry", to=to_email, attempt=self.request.retries)
        raise self.retry(countdown=30 * (self.request.retries + 1))


async def _send_payslip_email(payslip_id: str, organization_id: str, period_label: str) -> bool:
    async with get_db_context() as db:
        payroll_service = PayrollService(db)
        employee_repo = EmployeeRepository(db)

        payslip = await payroll_service.get_payslip(uuid.UUID(payslip_id))
        employee = await employee_repo.get_by_id(payslip.employee_id, uuid.UUID(organization_id))
        if not employee or not employee.email:
            logger.warning("payslip_email_skipped_no_email", payslip_id=payslip_id)
            return True  # nothing to retry -- there's no address to send to

        pdf_bytes = await payroll_service.get_payslip_pdf(uuid.UUID(payslip_id), uuid.UUID(organization_id))
        subject, text, html = payslip_ready_email(employee.full_name, period_label)
        filename = f"payslip-{period_label.replace(' ', '-').lower()}.pdf"
        return await email_service.send(
            employee.email, subject, text, html,
            attachments=[EmailAttachment(filename, pdf_bytes, "application/pdf")],
        )


@celery_app.task(name="payroll.send_payslip_email", bind=True, max_retries=3)
def send_payslip_email_task(self, payslip_id: str, organization_id: str, period_label: str) -> None:
    success = run_async(_send_payslip_email(payslip_id, organization_id, period_label))
    if not success:
        logger.warning("payslip_email_retry", payslip_id=payslip_id, attempt=self.request.retries)
        raise self.retry(countdown=30 * (self.request.retries + 1))
