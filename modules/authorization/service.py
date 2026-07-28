"""
Authorization module — service layer.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.authorization.models import Role
from modules.authorization.repository import AuthorizationRepository

logger = get_logger(__name__)

# Every module registers the permission codes it needs here as it's built.
# Seeded once via `seed_default_rbac`; safe to re-run (idempotent upserts).
DEFAULT_PERMISSIONS: list[tuple[str, str, str]] = [
    # (code, module, description)
    ("authorization.roles.view", "authorization", "View roles and their permissions"),
    ("authorization.roles.manage", "authorization", "Create, update, and delete roles"),
    ("authorization.roles.assign", "authorization", "Assign or revoke roles for users"),
    ("users.view", "users", "View user accounts and profiles"),
    ("users.manage", "users", "Suspend, deactivate, or edit user accounts and profiles"),
    ("organizations.view", "organizations", "View organizations"),
    ("organizations.manage", "organizations", "Create, update, and delete organizations"),
    ("branches.view", "branches", "View branches"),
    ("branches.manage", "branches", "Create, update, and delete branches"),
    ("settings.view", "settings", "View organization settings"),
    ("settings.manage", "settings", "Update organization settings"),
    ("dashboard.view", "dashboard", "View the dashboard summary"),
    ("crm.leads.view", "crm", "View CRM leads"),
    ("crm.leads.manage", "crm", "Create, update, and change status of CRM leads"),
    ("crm.enquiries.view", "crm", "View lead enquiries"),
    ("crm.enquiries.manage", "crm", "Create, update, and delete lead enquiries"),
    ("crm.followups.view", "crm", "View lead follow-ups"),
    ("crm.followups.manage", "crm", "Create, update, complete, and delete lead follow-ups"),
    ("crm.counselling.view", "crm", "View counselling sessions"),
    ("crm.counselling.manage", "crm", "Create, update, complete, and delete counselling sessions"),
    ("crm.admissions.view", "crm", "View admissions"),
    ("crm.admissions.manage", "crm", "Create, update, and cancel admissions"),
    ("students.view", "students", "View student records"),
    ("students.manage", "students", "Enroll, update, and manage student records"),
    ("courses.categories.view", "courses", "View course categories"),
    ("courses.categories.manage", "courses", "Create, update, and delete course categories"),
    ("courses.view", "courses", "View courses, chapters, lessons, and resources"),
    ("courses.manage", "courses", "Create, update, publish, and delete courses, chapters, lessons, and resources"),
    ("courses.learning_paths.view", "courses", "View learning paths"),
    ("courses.learning_paths.manage", "courses", "Create, update, and delete learning paths"),
    ("lms.enrollment.view", "lms", "View course enrollments"),
    ("lms.enrollment.manage", "lms", "Enroll and update student enrollment status"),
    ("lms.progress.view", "lms", "View student course progress"),
    ("lms.progress.manage", "lms", "Mark lessons complete/incomplete for students"),
    ("lms.assignments.view", "lms", "View assignments and submissions"),
    ("lms.assignments.manage", "lms", "Create, update, delete assignments and grade submissions"),
    ("lms.assignments.submit", "lms", "Submit an assignment on behalf of a student"),
    ("lms.assessments.view", "lms", "View quizzes, mock tests, and coding tests"),
    ("lms.assessments.manage", "lms", "Create, update, and delete assessments"),
    ("lms.assessments.attempt", "lms", "Start and submit assessment attempts"),
    ("lms.certificates.view", "lms", "View issued certificates"),
    ("lms.certificates.manage", "lms", "Issue certificates"),
    ("lms.announcements.view", "lms", "View announcements"),
    ("lms.announcements.manage", "lms", "Create, update, and delete announcements"),
    ("lms.discussions.participate", "lms", "Create discussion threads and replies"),
    ("lms.badges.view", "lms", "View badges"),
    ("lms.badges.manage", "lms", "Create badges and award them to students"),
    ("lms.transcripts.view", "lms", "View a student's aggregated academic transcript"),
    ("examinations.question_bank.view", "examinations", "View the question bank"),
    ("examinations.question_bank.manage", "examinations", "Create, update, and delete questions"),
    ("examinations.exams.view", "examinations", "View exams and their composition"),
    ("examinations.exams.manage", "examinations", "Create, update, delete exams and manage their questions"),
    ("examinations.evaluation.attempt", "examinations", "Start and submit exam attempts on behalf of a student"),
    ("examinations.evaluation.view", "examinations", "View exam attempts and answers"),
    ("examinations.evaluation.grade", "examinations", "Grade answers and finalize exam attempts"),
    ("examinations.practicals.view", "examinations", "View practical exams and results"),
    ("examinations.practicals.manage", "examinations", "Create practical exams and record results"),
    ("examinations.viva.view", "examinations", "View viva exams and results"),
    ("examinations.viva.manage", "examinations", "Create viva exams and record results"),
    ("examinations.results.view", "examinations", "View aggregated student results"),
    ("pentrix.labs.view", "pentrix", "View the lab catalog"),
    ("pentrix.labs.manage", "pentrix", "Create, update, and delete labs"),
    ("pentrix.instances.view", "pentrix", "View lab instances"),
    ("pentrix.instances.launch", "pentrix", "Launch and stop lab instances for students"),
    ("pentrix.challenges.view", "pentrix", "View challenges"),
    ("pentrix.challenges.manage", "pentrix", "Create, update, delete challenges, hints, and flags"),
    ("pentrix.flags.submit", "pentrix", "Submit flags and view hints on behalf of a student"),
    ("pentrix.leaderboard.view", "pentrix", "View the Pentrix leaderboard"),
    ("pentrix.achievements.view", "pentrix", "View achievements"),
    ("pentrix.achievements.manage", "pentrix", "Create achievements"),
    ("pentrix.certifications.view", "pentrix", "View issued Pentrix certifications"),
    ("pentrix.certifications.manage", "pentrix", "Issue Pentrix certifications"),
    ("accounting.ledger.view", "accounting", "View the chart of accounts and account balances"),
    ("accounting.ledger.manage", "accounting", "Create, update, and deactivate accounts"),
    ("accounting.journals.view", "accounting", "View journal entries"),
    ("accounting.journals.manage", "accounting", "Create, post, and reverse journal entries"),
    ("accounting.customers.view", "accounting", "View accounts-receivable customers"),
    ("accounting.customers.manage", "accounting", "Create, update, and delete customers"),
    ("accounting.vendors.view", "accounting", "View accounts-payable vendors"),
    ("accounting.vendors.manage", "accounting", "Create, update, and delete vendors"),
    ("accounting.gst.view", "accounting", "View GST rates and returns"),
    ("accounting.gst.manage", "accounting", "Create and update GST rates"),
    ("accounting.tds.view", "accounting", "View TDS sections and deductions"),
    ("accounting.tds.manage", "accounting", "Create and update TDS sections"),
    ("accounting.invoices.view", "accounting", "View sales invoices"),
    ("accounting.invoices.manage", "accounting", "Create, update, post, and cancel invoices"),
    ("accounting.receipts.view", "accounting", "View payment receipts"),
    ("accounting.receipts.manage", "accounting", "Record and void payment receipts"),
    ("accounting.expenses.view", "accounting", "View expenses"),
    ("accounting.expenses.manage", "accounting", "Create, update, and cancel expenses"),
    ("accounting.expenses.approve", "accounting", "Approve or reject submitted expenses"),
    ("accounting.payments.view", "accounting", "View vendor payments"),
    ("accounting.payments.manage", "accounting", "Record and void vendor payments"),
    ("accounting.bank.view", "accounting", "View bank accounts and transactions"),
    ("accounting.bank.manage", "accounting", "Create bank accounts and record bank transactions"),
    ("accounting.bank.reconcile", "accounting", "Reconcile bank transactions"),
    ("accounting.reports.view", "accounting", "View financial reports"),
    ("employees.view", "employees", "View employee records"),
    ("employees.manage", "employees", "Create, update, and offboard employee records"),
    ("hr.departments.view", "hr", "View departments"),
    ("hr.departments.manage", "hr", "Create, update, and deactivate departments"),
    ("hr.designations.view", "hr", "View designations"),
    ("hr.designations.manage", "hr", "Create, update, and deactivate designations"),
    ("attendance.view", "attendance", "View attendance records"),
    ("attendance.manage", "attendance", "Record check-in/check-out, mark, and regularize attendance"),
    ("leave.types.view", "leave", "View leave types"),
    ("leave.types.manage", "leave", "Create and update leave types"),
    ("leave.applications.view", "leave", "View leave applications and balances"),
    ("leave.applications.apply", "leave", "Apply for and cancel own leave applications"),
    ("leave.applications.approve", "leave", "Approve or reject leave applications"),
    ("payroll.components.view", "payroll", "View salary components"),
    ("payroll.components.manage", "payroll", "Create and update salary components"),
    ("payroll.structures.view", "payroll", "View employee salary structures"),
    ("payroll.structures.manage", "payroll", "Create employee salary structures"),
    ("payroll.runs.view", "payroll", "View payroll runs and payslips"),
    ("payroll.runs.manage", "payroll", "Generate and cancel payroll runs"),
    ("payroll.runs.finalize", "payroll", "Finalize payroll runs and mark them paid"),
    ("inventory.items.view", "inventory", "View item categories and inventory items"),
    ("inventory.items.manage", "inventory", "Create and update item categories and inventory items"),
    ("inventory.warehouses.view", "inventory", "View warehouses"),
    ("inventory.warehouses.manage", "inventory", "Create and update warehouses"),
    ("inventory.stock.view", "inventory", "View stock levels and transactions"),
    ("inventory.stock.manage", "inventory", "Receive, issue, adjust, and transfer stock"),
    ("assets.view", "assets", "View asset categories and the asset register"),
    ("assets.manage", "assets", "Create and update asset categories and assets"),
    ("assets.dispose", "assets", "Dispose of assets"),
    ("assets.depreciation.view", "assets", "View depreciation runs and entries"),
    ("assets.depreciation.manage", "assets", "Generate, post, and cancel depreciation runs"),
    ("procurement.purchase_orders.view", "procurement", "View purchase orders"),
    ("procurement.purchase_orders.manage", "procurement", "Create, update, send, and cancel purchase orders"),
    ("procurement.goods_receipts.view", "procurement", "View goods receipts"),
    ("procurement.goods_receipts.manage", "procurement", "Record goods receipts against purchase orders"),
    ("corporate.clients.view", "corporate", "View corporate clients"),
    ("corporate.clients.manage", "corporate", "Create, update, and delete corporate clients"),
    ("corporate.projects.view", "corporate", "View corporate projects"),
    ("corporate.projects.manage", "corporate", "Create and update corporate projects"),
    ("corporate.quotations.view", "corporate", "View quotations"),
    ("corporate.quotations.manage", "corporate", "Create, send, accept, and reject quotations"),
    ("corporate.contracts.view", "corporate", "View contracts"),
    ("corporate.contracts.manage", "corporate", "Create, activate, renew, and terminate contracts"),
    ("corporate.tickets.view", "corporate", "View support tickets"),
    ("corporate.tickets.manage", "corporate", "Create, update, and comment on support tickets"),
    ("corporate.amc.view", "corporate", "View AMC contracts and visits"),
    ("corporate.amc.manage", "corporate", "Create AMC contracts and manage visits"),
    ("corporate.vapt.view", "corporate", "View VAPT engagements and findings"),
    ("corporate.vapt.manage", "corporate", "Create and update VAPT engagements and findings"),
    ("corporate.soc.view", "corporate", "View SOC services and incidents"),
    ("corporate.soc.manage", "corporate", "Create and update SOC services and incidents"),
    ("corporate.reports.view", "corporate", "View corporate reports"),
    ("marketing.campaigns.view", "marketing", "View marketing campaigns"),
    ("marketing.campaigns.manage", "marketing", "Create, update, and change status of campaigns"),
    ("marketing.landing_pages.view", "marketing", "View landing pages and their stats"),
    ("marketing.landing_pages.manage", "marketing", "Create, update, publish, and archive landing pages"),
    ("marketing.coupons.view", "marketing", "View coupons and redemptions"),
    ("marketing.coupons.manage", "marketing", "Create and update coupons"),
    ("marketing.coupons.redeem", "marketing", "Validate and redeem coupons"),
    ("marketing.referrals.view", "marketing", "View referral programs and referrals"),
    ("marketing.referrals.manage", "marketing", "Create referral programs, submit, convert, and reward referrals"),
    ("marketing.analytics.view", "marketing", "View marketing analytics"),
    ("ai.conversations.use", "ai", "Use the AI Tutor and AI Chat Assistant"),
    ("ai.questions.generate", "ai", "Generate and review AI question drafts"),
    ("ai.questions.approve", "ai", "Approve AI-generated questions into the question bank"),
    ("ai.resumes.generate", "ai", "Use the AI Resume Builder"),
    ("ai.interviews.use", "ai", "Use the AI Interview Simulator"),
    ("ai.evaluations.generate", "ai", "Use AI Assignment Evaluation"),
    ("ai.recommendations.use", "ai", "Use AI Course Recommendation"),
    ("ai.analytics.view", "ai", "View AI-generated insight reports"),
    ("ai.analytics.generate", "ai", "Generate AI insight reports"),
    ("reports.run", "reports", "Browse the report catalog, run reports, and view execution history"),
    ("reports.schedule", "reports", "Create, update, and deactivate scheduled report emails"),
    ("audit.view", "audit", "View the organization's audit trail"),
    ("documents.view", "documents", "View and download uploaded documents"),
    ("documents.manage", "documents", "Upload and delete documents"),
    ("trainers.view", "trainers", "View trainer profiles"),
    ("trainers.manage", "trainers", "Create, update, and delete trainer profiles"),
    ("classrooms.view", "classrooms", "View classrooms"),
    ("classrooms.manage", "classrooms", "Create, update, and delete classrooms"),
    ("batches.view", "batches", "View batches"),
    ("batches.manage", "batches", "Create, update, and delete batches"),
    ("timetable.view", "timetable", "View timetable entries"),
    ("timetable.manage", "timetable", "Create, update, and delete timetable entries"),
    ("live_classes.view", "live_classes", "View live classes"),
    ("live_classes.manage", "live_classes", "Create, update, delete, and change status of live classes"),
    ("workshops.view", "workshops", "View workshops and their registrations"),
    ("workshops.manage", "workshops", "Create, update, delete workshops and manage registrations"),
    ("hackathons.view", "hackathons", "View hackathons, teams, and submissions"),
    ("hackathons.manage", "hackathons", "Create, update, delete hackathons and grade submissions"),
    ("placements.view", "placements", "View companies, job postings, and applications"),
    ("placements.manage", "placements", "Create, update, delete companies/postings and manage applications"),
    ("internships.view", "internships", "View internship postings, applications, and active internships"),
    (
        "internships.manage",
        "internships",
        "Create, update, delete internship postings and manage applications/internships",
    ),
    ("alumni.view", "alumni", "View alumni profiles, events, and job referrals"),
    (
        "alumni.manage",
        "alumni",
        "Verify alumni profiles, manage events/registrations, and moderate job referrals",
    ),
    ("media.view", "media", "View media albums and assets"),
    ("media.manage", "media", "Create, update, delete media albums and upload/manage assets"),
    ("workflow.view", "workflow", "View approval workflows and requests"),
    ("workflow.manage", "workflow", "Create, update, and delete approval workflow configurations"),
    ("notifications.manage", "notifications", "Broadcast in-app notifications to everyone in the organization"),
    ("communication.view", "communication", "View the outbound email/SMS/WhatsApp communication log"),
    ("communication.manage", "communication", "Send email/SMS/WhatsApp communications"),
    ("events.manage", "events", "Create, update, and delete org-wide calendar events"),
    ("backups.view", "backups", "View database backup job history"),
    ("backups.manage", "backups", "Trigger and download full database backups"),
    ("integrations.view", "integrations", "View configured third-party integrations"),
    ("integrations.manage", "integrations", "Create, update, delete, and test third-party integrations"),
    ("monitoring.view", "monitoring", "View live system health checks and platform-wide statistics"),
]

# Backups, Integrations, and Monitoring are deliberately NOT added to the
# "Staff" role's permission list below — a full database dump (every
# organization's data), stored third-party API keys, and infrastructure
# health/connection-pool internals are all Administrator/Super Admin only.

# System roles that ship with the platform and cannot be deleted.
SYSTEM_ROLES: list[tuple[str, str, str, list[str]]] = [
    (
        "Super Admin",
        "super_admin",
        "Full platform access. Bypasses permission checks entirely (is_superuser=True).",
        [],  # Super Admins rely on User.is_superuser, not an explicit permission list.
    ),
    (
        "Administrator",
        "administrator",
        "Broad administrative access across modules.",
        [code for code, _, _ in DEFAULT_PERMISSIONS],
    ),
    (
        "Staff",
        "staff",
        "Standard staff access with no administrative privileges by default.",
        [
            "dashboard.view",
            "crm.leads.view",
            "crm.leads.manage",
            "crm.enquiries.view",
            "crm.enquiries.manage",
            "crm.followups.view",
            "crm.followups.manage",
            "crm.counselling.view",
            "crm.counselling.manage",
            "crm.admissions.view",
            "students.view",
            "students.manage",
            "courses.categories.view",
            "courses.view",
            "courses.learning_paths.view",
            "lms.enrollment.view",
            "lms.enrollment.manage",
            "lms.progress.view",
            "lms.progress.manage",
            "lms.assignments.view",
            "lms.assignments.manage",
            "lms.assessments.view",
            "lms.assessments.attempt",
            "lms.certificates.view",
            "lms.certificates.manage",
            "lms.announcements.view",
            "lms.announcements.manage",
            "lms.discussions.participate",
            "lms.badges.view",
            "lms.badges.manage",
            "lms.transcripts.view",
            "examinations.question_bank.view",
            "examinations.question_bank.manage",
            "examinations.exams.view",
            "examinations.evaluation.attempt",
            "examinations.evaluation.view",
            "examinations.evaluation.grade",
            "examinations.practicals.view",
            "examinations.practicals.manage",
            "examinations.viva.view",
            "examinations.viva.manage",
            "examinations.results.view",
            "pentrix.labs.view",
            "pentrix.instances.view",
            "pentrix.instances.launch",
            "pentrix.challenges.view",
            "pentrix.challenges.manage",
            "pentrix.flags.submit",
            "pentrix.leaderboard.view",
            "pentrix.achievements.view",
            "pentrix.achievements.manage",
            "pentrix.certifications.view",
            "pentrix.certifications.manage",
            # Accounting: view-only by default. Financial posting/approval
            # permissions (manage/approve) are reserved for an
            # organization-defined Accountant role, not granted to Staff.
            "accounting.ledger.view",
            "accounting.journals.view",
            "accounting.customers.view",
            "accounting.vendors.view",
            "accounting.gst.view",
            "accounting.tds.view",
            "accounting.invoices.view",
            "accounting.receipts.view",
            "accounting.expenses.view",
            "accounting.payments.view",
            "accounting.bank.view",
            "accounting.reports.view",
            "employees.view",
            "hr.departments.view",
            "hr.designations.view",
            "attendance.view",
            "attendance.manage",
            "leave.types.view",
            "leave.applications.view",
            "leave.applications.apply",
            "inventory.items.view",
            "inventory.warehouses.view",
            "inventory.stock.view",
            "assets.view",
            "assets.depreciation.view",
            "procurement.purchase_orders.view",
            "procurement.goods_receipts.view",
            "corporate.clients.view",
            "corporate.projects.view",
            "corporate.quotations.view",
            "corporate.contracts.view",
            "corporate.tickets.view",
            "corporate.tickets.manage",
            "corporate.amc.view",
            "corporate.vapt.view",
            "corporate.soc.view",
            "corporate.reports.view",
            "marketing.campaigns.view",
            "marketing.landing_pages.view",
            "marketing.coupons.view",
            "marketing.coupons.redeem",
            "marketing.referrals.view",
            "marketing.referrals.manage",
            "marketing.analytics.view",
            "ai.conversations.use",
            "ai.questions.generate",
            "ai.resumes.generate",
            "ai.interviews.use",
            "ai.evaluations.generate",
            "ai.recommendations.use",
            "ai.analytics.view",
            "reports.run",
            "documents.view",
            "documents.manage",
            "trainers.view",
            "classrooms.view",
            "batches.view",
            "timetable.view",
            "live_classes.view",
            "live_classes.manage",
            "workshops.view",
            "workshops.manage",
            "hackathons.view",
            "hackathons.manage",
            "placements.view",
            "placements.manage",
            "internships.view",
            "internships.manage",
            "alumni.view",
            "alumni.manage",
            "media.view",
            "media.manage",
            "workflow.view",
            "workflow.manage",
            "communication.view",
            "communication.manage",
            "events.manage",
        ],
    ),
]

# Notifications broadcast is Administrator-only (not curated into Staff's
# default permission list above) — spamming every org member is a
# sensitive action, unlike viewing/reading one's own notification tray
# which needs no permission at all (ownership is the authorization).


class AuthorizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuthorizationRepository(db)

    # ---- Roles ----

    async def create_role(self, name: str, slug: str, description: str | None) -> Role:
        existing = await self.repo.get_role_by_slug(slug)
        if existing:
            raise ConflictError(f"A role with slug '{slug}' already exists.")
        role = await self.repo.create_role(name, slug, description)
        logger.info("role_created", role_id=str(role.id), slug=slug)
        return role

    async def update_role(self, role_id: uuid.UUID, name: str | None, description: str | None) -> Role:
        role = await self.repo.get_role_by_id(role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        if role.is_system and name is not None:
            raise ValidationError("System roles cannot be renamed.")
        return await self.repo.update_role(role, name, description)

    async def delete_role(self, role_id: uuid.UUID) -> None:
        role = await self.repo.get_role_by_id(role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        if role.is_system:
            raise ValidationError("System roles cannot be deleted.")
        await self.repo.delete_role(role)
        logger.info("role_deleted", role_id=str(role_id))

    async def get_role_with_permissions(self, role_id: uuid.UUID) -> Role:
        role = await self.repo.get_role_with_permissions(role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        return role

    async def list_roles(self) -> list[Role]:
        return await self.repo.list_roles()

    async def list_permissions(self):
        return await self.repo.list_permissions()

    # ---- Role <-> Permission ----

    async def set_role_permissions(self, role_id: uuid.UUID, permission_codes: list[str]) -> Role:
        role = await self.repo.get_role_by_id(role_id)
        if not role:
            raise NotFoundError("Role", role_id)

        permissions = await self.repo.get_permissions_by_codes(permission_codes)
        found_codes = {p.code for p in permissions}
        missing = set(permission_codes) - found_codes
        if missing:
            raise ValidationError(f"Unknown permission code(s): {', '.join(sorted(missing))}")

        await self.repo.set_role_permissions(role, permissions)
        logger.info("role_permissions_updated", role_id=str(role_id), permissions=list(found_codes))
        return await self.repo.get_role_with_permissions(role_id)

    # ---- User <-> Role ----

    async def assign_role(
        self, user_id: uuid.UUID, role_id: uuid.UUID, assigned_by_user_id: uuid.UUID | None
    ) -> None:
        role = await self.repo.get_role_by_id(role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        await self.repo.assign_role(user_id, role_id, assigned_by_user_id)
        logger.info("role_assigned", user_id=str(user_id), role_id=str(role_id))

    async def revoke_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        await self.repo.revoke_role(user_id, role_id)
        logger.info("role_revoked", user_id=str(user_id), role_id=str(role_id))

    async def get_user_roles_and_permissions(self, user_id: uuid.UUID) -> dict:
        roles = await self.repo.get_roles_for_user(user_id)
        permissions = await self.repo.get_permission_codes_for_user(user_id)
        return {"roles": roles, "effective_permissions": sorted(permissions)}

    # ---- Seeding ----

    async def seed_default_rbac(self) -> None:
        """
        Idempotently ensures the default permission set and system roles
        exist. Safe to call on every startup; called once from a seed
        script (`database/seeds`), not automatically on every boot.
        """
        permission_map = {}
        for code, module, description in DEFAULT_PERMISSIONS:
            permission_map[code] = await self.repo.get_or_create_permission(code, module, description)

        for name, slug, description, codes in SYSTEM_ROLES:
            role = await self.repo.get_role_by_slug(slug)
            if not role:
                role = await self.repo.create_role(name, slug, description)
                role.is_system = True
                await self.db.flush()
            if codes:
                permissions = [permission_map[c] for c in codes]
                await self.repo.set_role_permissions(role, permissions)

        logger.info("rbac_seed_complete")
