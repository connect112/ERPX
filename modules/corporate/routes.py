"""
Corporate module — top-level router aggregator.

Mounted at /corporate. Every sub-resource keeps its own routes.py,
consistent with how Accounting, CRM, and Pentrix aggregate their
sub-routers.
"""

from fastapi import APIRouter

from modules.corporate.amc.routes import router as amc_router
from modules.corporate.clients.routes import router as clients_router
from modules.corporate.contracts.routes import router as contracts_router
from modules.corporate.projects.routes import router as projects_router
from modules.corporate.quotations.routes import router as quotations_router
from modules.corporate.reports.routes import router as reports_router
from modules.corporate.soc.routes import router as soc_router
from modules.corporate.tickets.routes import router as tickets_router
from modules.corporate.vapt.routes import router as vapt_router

router = APIRouter()

router.include_router(clients_router, prefix="/clients", tags=["Corporate - Clients"])
router.include_router(projects_router, prefix="/projects", tags=["Corporate - Projects"])
router.include_router(quotations_router, prefix="/quotations", tags=["Corporate - Quotations"])
router.include_router(contracts_router, prefix="/contracts", tags=["Corporate - Contracts"])
router.include_router(tickets_router, prefix="/tickets", tags=["Corporate - Tickets"])
router.include_router(amc_router, prefix="/amc", tags=["Corporate - AMC"])
router.include_router(vapt_router, prefix="/vapt", tags=["Corporate - VAPT"])
router.include_router(soc_router, prefix="/soc", tags=["Corporate - SOC"])
router.include_router(reports_router, prefix="/reports", tags=["Corporate - Reports"])
