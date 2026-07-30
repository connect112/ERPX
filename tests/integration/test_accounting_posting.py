"""
Integration test for Accounting's central invariant: every posted
journal entry balances (total debit == total credit), and posting an
Invoice through the real API produces a correctly balanced entry that
flows through to the account balance and the org-wide trial balance.

This exercises Ledger, Journals, Customers, GST, and Invoices together
through actual HTTP requests — the same posting path a real invoice
would take in production — rather than calling service methods directly.
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]


async def _create_account(client, auth_headers, code, name, account_type):
    response = await client.post(
        "/api/v1/accounting/accounts",
        json={"code": code, "name": name, "account_type": account_type},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_customer(client, auth_headers, code="CUST-001"):
    response = await client.post(
        "/api/v1/accounting/customers",
        json={"customer_code": code, "name": "Acme Corp", "customer_type": "corporate"},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def chart_of_accounts(client, auth_headers):
    receivable = await _create_account(client, auth_headers, "1200", "Accounts Receivable", "asset")
    revenue = await _create_account(client, auth_headers, "4000", "Course Fee Income", "income")
    tax_payable = await _create_account(client, auth_headers, "2100", "GST Payable", "liability")
    return {"receivable": receivable, "revenue": revenue, "tax_payable": tax_payable}


async def test_posting_simple_invoice_produces_balanced_journal_entry(client, auth_headers, chart_of_accounts):
    customer = await _create_customer(client, auth_headers)

    create_response = await client.post(
        "/api/v1/accounting/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-1001",
            "invoice_date": "2026-01-15T00:00:00Z",
            "due_date": "2026-02-15T00:00:00Z",
            "receivable_account_id": chart_of_accounts["receivable"]["id"],
            "lines": [
                {
                    "revenue_account_id": chart_of_accounts["revenue"]["id"],
                    "description": "Full Stack Web Development course",
                    "quantity": 1,
                    "unit_price": 25000,
                }
            ],
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    invoice = create_response.json()
    assert invoice["status"] == "draft"
    assert invoice["total_amount"] == 25000.0

    post_response = await client.post(
        f"/api/v1/accounting/invoices/{invoice['id']}/post", headers=auth_headers
    )
    assert post_response.status_code == 200, post_response.text
    posted = post_response.json()
    assert posted["status"] == "sent"
    assert posted["journal_entry_id"] is not None

    journal_response = await client.get(
        f"/api/v1/accounting/journals/{posted['journal_entry_id']}", headers=auth_headers
    )
    assert journal_response.status_code == 200
    entry = journal_response.json()
    assert entry["status"] == "posted"

    total_debit = sum(line["debit"] for line in entry["lines"])
    total_credit = sum(line["credit"] for line in entry["lines"])
    assert total_debit == total_credit == 25000.0

    receivable_line = next(l for l in entry["lines"] if l["account_id"] == chart_of_accounts["receivable"]["id"])
    revenue_line = next(l for l in entry["lines"] if l["account_id"] == chart_of_accounts["revenue"]["id"])
    assert receivable_line["debit"] == 25000.0 and receivable_line["credit"] == 0
    assert revenue_line["credit"] == 25000.0 and revenue_line["debit"] == 0

    balance_response = await client.get(
        f"/api/v1/accounting/accounts/{chart_of_accounts['receivable']['id']}/balance", headers=auth_headers
    )
    assert balance_response.status_code == 200
    balance = balance_response.json()
    assert balance["closing_balance"] == 25000.0


async def test_invoice_with_gst_computes_tax_and_stays_balanced(client, auth_headers, chart_of_accounts):
    customer = await _create_customer(client, auth_headers, code="CUST-002")

    gst_response = await client.post(
        "/api/v1/accounting/gst/rates",
        json={"name": "GST 18%", "rate_percent": 18},
        headers=auth_headers,
    )
    assert gst_response.status_code == 201, gst_response.text
    gst_rate = gst_response.json()

    create_response = await client.post(
        "/api/v1/accounting/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-1002",
            "invoice_date": "2026-01-15T00:00:00Z",
            "due_date": "2026-02-15T00:00:00Z",
            "receivable_account_id": chart_of_accounts["receivable"]["id"],
            "tax_payable_account_id": chart_of_accounts["tax_payable"]["id"],
            "is_interstate": False,
            "lines": [
                {
                    "revenue_account_id": chart_of_accounts["revenue"]["id"],
                    "description": "Cybersecurity Bootcamp",
                    "quantity": 1,
                    "unit_price": 10000,
                    "gst_rate_id": gst_rate["id"],
                }
            ],
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    invoice = create_response.json()

    # Intra-state 18% splits evenly into CGST 9% + SGST 9% = 1800 total tax.
    assert invoice["subtotal_amount"] == 10000.0
    assert invoice["tax_amount"] == 1800.0
    assert invoice["total_amount"] == 11800.0

    post_response = await client.post(f"/api/v1/accounting/invoices/{invoice['id']}/post", headers=auth_headers)
    assert post_response.status_code == 200

    trial_balance_response = await client.get(
        "/api/v1/accounting/reports/trial-balance",
        params={"as_of_date": "2026-12-31"},
        headers=auth_headers,
    )
    assert trial_balance_response.status_code == 200
    trial_balance = trial_balance_response.json()
    assert trial_balance["is_balanced"] is True
    assert trial_balance["total_debit"] == trial_balance["total_credit"]


async def test_cannot_post_invoice_twice(client, auth_headers, chart_of_accounts):
    customer = await _create_customer(client, auth_headers, code="CUST-003")
    create_response = await client.post(
        "/api/v1/accounting/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-1003",
            "invoice_date": "2026-01-15T00:00:00Z",
            "due_date": "2026-02-15T00:00:00Z",
            "receivable_account_id": chart_of_accounts["receivable"]["id"],
            "lines": [
                {
                    "revenue_account_id": chart_of_accounts["revenue"]["id"],
                    "description": "Data Science course",
                    "quantity": 1,
                    "unit_price": 5000,
                }
            ],
        },
        headers=auth_headers,
    )
    invoice = create_response.json()

    first_post = await client.post(f"/api/v1/accounting/invoices/{invoice['id']}/post", headers=auth_headers)
    assert first_post.status_code == 200

    second_post = await client.post(f"/api/v1/accounting/invoices/{invoice['id']}/post", headers=auth_headers)
    assert second_post.status_code == 422


async def test_ar_aging_report_resolves_customer_name_via_join(client, auth_headers, chart_of_accounts):
    """AR aging must report each outstanding invoice with its customer's
    name and correct totals. Guards the JOIN-based
    ReportsRepository.outstanding_receivables_with_customer that replaced a
    per-invoice N+1 customer lookup (finding #17 SQL-aggregation pass)."""
    customer = await _create_customer(client, auth_headers, code="CUST-AGE")

    create_response = await client.post(
        "/api/v1/accounting/invoices",
        json={
            "customer_id": customer["id"],
            "invoice_number": "INV-AGE-1",
            "invoice_date": "2026-01-15T00:00:00Z",
            "due_date": "2026-02-15T00:00:00Z",
            "receivable_account_id": chart_of_accounts["receivable"]["id"],
            "lines": [
                {
                    "revenue_account_id": chart_of_accounts["revenue"]["id"],
                    "description": "Aging test course",
                    "quantity": 1,
                    "unit_price": 12000,
                }
            ],
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201, create_response.text
    invoice = create_response.json()
    post_response = await client.post(
        f"/api/v1/accounting/invoices/{invoice['id']}/post", headers=auth_headers
    )
    assert post_response.status_code == 200, post_response.text

    aging = await client.get(
        "/api/v1/accounting/reports/aging/receivables?as_of_date=2026-03-31", headers=auth_headers
    )
    assert aging.status_code == 200, aging.text
    body = aging.json()

    mine = [item for item in body["items"] if item["document_number"] == "INV-AGE-1"]
    assert len(mine) == 1
    item = mine[0]
    assert item["party_name"] == "Acme Corp"  # resolved via the JOIN, not "Unknown"
    assert item["party_id"] == customer["id"]
    assert item["outstanding_amount"] == 12000.0
    assert body["total_outstanding"] >= 12000.0
    assert sum(body["bucket_totals"].values()) == pytest.approx(body["total_outstanding"])
