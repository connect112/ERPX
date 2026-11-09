"""Regenerates the two genuine PDFs the browser tests show, with the real receipt renderer (no mocks).

    PYTHONPATH=<repo root> python apps/web/e2e/fixtures/make_receipt_pdfs.py

``receipt-sample.pdf`` is a sample tax invoice (what the designer previews); ``receipt-issued.pdf`` is a payment receipt
(what Generated Receipts shows). Synthetic data only.
"""

from decimal import Decimal
from pathlib import Path

from modules.internship_onboarding import financial
from modules.internship_onboarding.receipt_design import ReceiptDesign
from modules.internship_onboarding.receipt_pdf import build_receipt_pdf

OUT = Path(__file__).parent


def details(kind: str) -> dict:
    amount = "5900.00"
    return {
        "kind": kind,
        "issuer": {"name": "GIR Technologies Pvt Ltd", "address": "Hyderabad, Telangana 500081", "gstin": "36ABCDE1234F1Z5" if kind == "tax_invoice" else None},
        "student": {"name": "Sample Student", "email": "student@example.com"},
        "application_reference": "ERPX-INT-2026-000001",
        "internship": "Cyber Security Internship",
        "description": "Internship programme fee",
        "method": "Online (Cashfree)",
        "transaction_reference": "SAMPLE-1234567890",
        "paid_on": "2026-11-09",
        "issued_on": "2026-11-09",
        "currency": "INR",
        "amount": amount,
        "tax": financial.tax_lines(Decimal(amount), {"tax_mode": "inclusive", "tax_rate_percent": "18", "tax_label": "GST"}) if kind == "tax_invoice" else None,
        "against": None,
        "footer": "",
    }


for kind, number, name, mark in (("tax_invoice", "SAMPLE-0001", "receipt-sample.pdf", "SAMPLE - NOT A VALID RECEIPT"), ("receipt", "RCPT-2026-000001", "receipt-issued.pdf", None)):
    data, pages = build_receipt_pdf(kind, number, details(kind), ReceiptDesign(), None, mark)
    (OUT / name).write_bytes(data)
    print(name, pages, "page(s)", len(data), "bytes")
