"""
CRM module — top-level router.

Combines every CRM sub-resource under a single /crm prefix. Leads is the
root resource (/crm/leads); Enquiries, Follow-ups, Counselling, and
Admissions all nest under a lead (/crm/leads/{lead_id}/...) since they
only make sense in that context, except Admissions' list view
(/crm/admissions) which spans the whole organization.
"""

from fastapi import APIRouter

from modules.crm.admissions.routes import router as admissions_router
from modules.crm.counselling.routes import router as counselling_router
from modules.crm.enquiries.routes import router as enquiries_router
from modules.crm.followups.routes import router as followups_router
from modules.crm.leads.routes import router as leads_router

router = APIRouter()

router.include_router(leads_router, prefix="/leads", tags=["CRM - Leads"])
router.include_router(enquiries_router, tags=["CRM - Enquiries"])
router.include_router(followups_router, tags=["CRM - Follow-ups"])
router.include_router(counselling_router, tags=["CRM - Counselling"])
router.include_router(admissions_router, tags=["CRM - Admissions"])
