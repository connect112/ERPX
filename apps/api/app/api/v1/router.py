"""
Top-level /api/v1 router.

Each module (authentication, users, crm, courses, accounting, ...) exposes
a FastAPI `APIRouter` from its own `routes.py` and gets included here as
that module is built. This file is the single wiring point for the whole
API surface, so the full set of live endpoints is always visible in one
place.

Example of how a module will register itself once built:

    from modules.authentication.routes import router as auth_router
    api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from modules.accounting.router import router as accounting_router
from modules.alumni.routes import router as alumni_router
from modules.ai.routes import router as ai_router
from modules.assets.routes import router as assets_router
from modules.attendance.routes import router as attendance_router
from modules.audit.routes import router as audit_router
from modules.authentication.routes import router as auth_router
from modules.backups.routes import router as backups_router
from modules.authorization.routes import router as authorization_router
from modules.batches.routes import router as batches_router
from modules.branches.routes import router as branches_router
from modules.classrooms.routes import router as classrooms_router
from modules.communication.routes import router as communication_router
from modules.corporate.routes import router as corporate_router
from modules.crm.routes import router as crm_router
from modules.courses.router import router as courses_router
from modules.dashboard.routes import router as dashboard_router
from modules.documents.routes import router as documents_router
from modules.employees.routes import router as employees_router
from modules.events.routes import router as events_router
from modules.examinations.router import router as examinations_router
from modules.hr.routes import router as hr_router
from modules.internships.routes import router as internships_router
from modules.integrations.routes import router as integrations_router
from modules.inventory.routes import router as inventory_router
from modules.leave.routes import router as leave_router
from modules.live_classes.routes import router as live_classes_router
from modules.lms.router import router as lms_router
from modules.marketing.routes import router as marketing_router
from modules.media.routes import router as media_router
from modules.monitoring.routes import router as monitoring_router
from modules.notifications.routes import router as notifications_router
from modules.organizations.routes import router as organizations_router
from modules.payroll.routes import router as payroll_router
from modules.pentrix.router import router as pentrix_router
from modules.procurement.routes import router as procurement_router
from modules.provisioning.routes import router as provisioning_router
from modules.reports.routes import router as reports_router
from modules.settings.routes import router as settings_router
from modules.students.routes import router as students_router
from modules.timetable.routes import router as timetable_router
from modules.trainers.routes import router as trainers_router
from modules.workflow.routes import router as workflow_router
from modules.hackathons.routes import router as hackathons_router
from modules.placements.routes import router as placements_router
from modules.users.routes import router as users_router
from modules.workshops.routes import router as workshops_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(authorization_router, prefix="/authorization", tags=["Authorization"])
api_router.include_router(organizations_router, prefix="/organizations", tags=["Organizations"])
api_router.include_router(branches_router, prefix="/branches", tags=["Branches"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(events_router, prefix="/events", tags=["Events"])
api_router.include_router(crm_router, prefix="/crm")
api_router.include_router(students_router, prefix="/students", tags=["Students"])
api_router.include_router(courses_router, prefix="/courses")
api_router.include_router(lms_router, prefix="/lms")
api_router.include_router(examinations_router, prefix="/examinations")
api_router.include_router(pentrix_router, prefix="/pentrix")
api_router.include_router(accounting_router, prefix="/accounting")
api_router.include_router(employees_router, prefix="/employees", tags=["Employees"])
api_router.include_router(hr_router, prefix="/hr", tags=["HR"])
api_router.include_router(attendance_router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(leave_router, prefix="/leave", tags=["Leave"])
api_router.include_router(payroll_router, prefix="/payroll", tags=["Payroll"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(assets_router, prefix="/assets", tags=["Assets"])
api_router.include_router(procurement_router, prefix="/procurement", tags=["Procurement"])
api_router.include_router(
    provisioning_router, prefix="/internal/provisioning", tags=["Internal - Provisioning"]
)
api_router.include_router(corporate_router, prefix="/corporate")
api_router.include_router(communication_router, prefix="/communication", tags=["Communication"])
api_router.include_router(marketing_router, prefix="/marketing")
api_router.include_router(ai_router, prefix="/ai", tags=["AI"])
api_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
api_router.include_router(audit_router, prefix="/audit", tags=["Audit"])
api_router.include_router(backups_router, prefix="/backups", tags=["Backups"])
api_router.include_router(integrations_router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(trainers_router, prefix="/trainers", tags=["Trainers"])
api_router.include_router(classrooms_router, prefix="/classrooms", tags=["Classrooms"])
api_router.include_router(batches_router, prefix="/batches", tags=["Batches"])
api_router.include_router(timetable_router, prefix="/timetable", tags=["Timetable"])
api_router.include_router(live_classes_router, prefix="/live-classes", tags=["Live Classes"])
api_router.include_router(workshops_router, prefix="/workshops", tags=["Workshops"])
api_router.include_router(hackathons_router, prefix="/hackathons", tags=["Hackathons"])
api_router.include_router(placements_router, prefix="/placements", tags=["Placements"])
api_router.include_router(internships_router, prefix="/internships", tags=["Internships"])
api_router.include_router(alumni_router, prefix="/alumni", tags=["Alumni"])
api_router.include_router(media_router, prefix="/media", tags=["Media"])
api_router.include_router(workflow_router, prefix="/workflow", tags=["Workflow"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["Monitoring"])

# ---------------------------------------------------------------------------
# Modules still being built out (portal apps, Workshops/Hackathons/
# Placements/..., etc.) register their routers here as each one is
# completed, following the exact pattern above.
# ---------------------------------------------------------------------------
