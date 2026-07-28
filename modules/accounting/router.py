"""
Accounting module — top-level router aggregator.

Mounted at /accounting. Sub-modules are unaware of each other's URL
prefixes and each expose their own `router.py`, kept consistent with how
Courses, LMS, Examinations, and Pentrix aggregate their sub-routers.
"""

from fastapi import APIRouter

from modules.accounting.bank.routes import router as bank_router
from modules.accounting.customers.routes import router as customers_router
from modules.accounting.expenses.routes import router as expenses_router
from modules.accounting.gst.routes import router as gst_router
from modules.accounting.invoices.routes import router as invoices_router
from modules.accounting.journals.routes import router as journals_router
from modules.accounting.ledger.routes import router as ledger_router
from modules.accounting.payments.routes import router as payments_router
from modules.accounting.receipts.routes import router as receipts_router
from modules.accounting.reports.routes import router as reports_router
from modules.accounting.tds.routes import router as tds_router
from modules.accounting.vendors.routes import router as vendors_router

router = APIRouter()

router.include_router(ledger_router, prefix="/accounts", tags=["Accounting - Ledger"])
router.include_router(journals_router, prefix="/journals", tags=["Accounting - Journals"])
router.include_router(customers_router, prefix="/customers", tags=["Accounting - Customers"])
router.include_router(vendors_router, prefix="/vendors", tags=["Accounting - Vendors"])
router.include_router(gst_router, prefix="/gst", tags=["Accounting - GST"])
router.include_router(tds_router, prefix="/tds", tags=["Accounting - TDS"])
router.include_router(invoices_router, prefix="/invoices", tags=["Accounting - Invoices"])
router.include_router(receipts_router, prefix="/receipts", tags=["Accounting - Receipts"])
router.include_router(expenses_router, prefix="/expenses", tags=["Accounting - Expenses"])
router.include_router(payments_router, prefix="/payments", tags=["Accounting - Payments"])
router.include_router(bank_router, prefix="/bank", tags=["Accounting - Bank"])
router.include_router(reports_router, prefix="/reports", tags=["Accounting - Reports"])
