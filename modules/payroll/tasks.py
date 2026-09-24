"""
Payroll module — background tasks.

Auto-generates each organization's monthly payroll draft on the last
working day of the month, then notifies that org's Administrator(s) both
in-app and by email — so the numbers are calculated and waiting for
review rather than something an admin has to remember to go click
"Generate run" for. Nothing is finalized or paid automatically; this
only ever produces a Draft run, exactly like a manual "Generate run"
click would (PayrollService.auto_generate_monthly_draft is a thin
wrapper around the same generate_run used by that button).
"""

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.authorization.repository import AuthorizationRepository
from modules.notifications.models import NotificationType
from modules.notifications.service import NotificationService
from modules.organizations.repository import OrganizationRepository
from modules.organizations.service import SYSTEM_ORG_SLUG
from modules.payroll.service import PayrollService
from packages.email.service import email_service
from packages.email.templates import payroll_draft_ready_email

logger = get_logger(__name__)

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


async def _auto_generate_for_all_organizations() -> int:
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
            run = await payroll_service.auto_generate_monthly_draft(org.id)
            if run is None:
                continue
            generated += 1

            period_label = f"{_MONTH_NAMES[run.period_month - 1]} {run.period_year}"
            review_url = f"{settings.FRONTEND_URL}/payroll/runs/{run.id}"
            admins = await authz_repo.list_users_with_role_in_organization(org.id, "administrator")
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
