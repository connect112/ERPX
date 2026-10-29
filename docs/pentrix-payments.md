# Pentrix payments in ERPX (Phase 4)

Pentrix → **Payments** lists every payment made on Pentrix, with the candidate, amount, date, method, transaction reference, status and
invoice. **Daily Summary** shows what was collected each calendar day in India and whether ERPX agrees with Pentrix about it.

## What this does, and does not do

* It **records and reports**. Nothing here moves money, starts a payment or marks one paid. A payment is "Paid" in ERPX only because
  Pentrix recorded it after its payment provider's signature-verified webhook (`PaymentService.handle_webhook`); a browser redirect or a
  user-submitted confirmation never counts.
* It does **not** post anything to ERPX's accounting ledger (journals, receipts, GST). That is a separate decision about how Pentrix
  income should be booked; the payment records are kept so it can be added.
* **Invoice numbers stay Pentrix's.** Pentrix numbers invoices (`INV-…`, issued when a token-fee payment succeeds) and receipts
  (`RCPT-…`); ERPX never numbers anything. Programme-fee payments currently have a receipt number but no invoice number in Pentrix; their
  document is titled "Payment receipt".
* Pentrix records the payment **provider** (Razorpay or Stripe), not the instrument (card, UPI…), so "Method" shows the provider.
* A **partial refund's amount is not recorded** in Pentrix, so partial refunds are counted but carry no amount in the daily totals.

## How payments stay in step

* **Real time:** the Pentrix database session notices a saved payment and, after the commit, sends it to
  `POST /api/v1/internal/pentrix/payments` (signed with the shared secret, best effort).
* **Pull:** every minute `pentrix.sync_payments` asks `GET /api/v1/internal/erpx/payments?cursor=` for everything changed since a saved
  cursor. *Refresh from Pentrix* runs it now; when the last attempt failed the same button reads *Retry synchronisation* and the page says
  why.
* **No duplicates:** a payment is matched only by Pentrix's payment id (unique), so a repeat, a push plus a pull, or two messages arriving
  at the same moment leave one row (`modules/pentrix_ops/mirror.py`). The original transaction reference is kept. An older message never
  overwrites a newer state.
* Pentrix now records **when** a payment succeeded, failed or was refunded (`payments.paid_at / failed_at / refunded_at`, migration
  `b8c9d0e1f2a3`), because a row's last-change time also moves for unrelated reasons (retrying provisioning, say).

## Daily summary and reconciliation

A day is midnight to midnight in India. For each day ERPX shows: successful payments and the amount collected (counted by when each was
paid), pending (started that day and still open), failed, refunds (count and amount of complete refunds, plus partial refunds), and the
net.

`pentrix.reconcile_payments` runs at **00:10 and 06:10 India time** (18:40 and 00:40 UTC). It reconciles the day that has just closed:

1. ask Pentrix for that day (`GET /payments/day/<date>`: totals and every payment involved);
2. compare payment by payment with ERPX's copy (missing here, status differs, amount differs, invoice differs, extra here);
3. **repair** each difference by fetching that payment from Pentrix again, then compare again;
4. record the outcome on the day's single summary row: *Matches Pentrix*, *Differences found* (listed, with what could not be repaired),
   or *Check failed* (Pentrix unreachable).

The two most recent closed days are always checked again (a webhook can arrive late), and so is any earlier day (up to 60 back) that never
matched. A person with `pentrix_ops.payments.manage` can **Reconcile now** for any closed day. Running it again rewrites that day's one
row, so nothing is counted twice. Today is shown live, labelled "in progress", and cannot be reconciled until it ends.

The daily summary and each day's payments **export as CSV** (names and references that start with `= + - @` are defused so a
spreadsheet does not run them as formulas).

## Permissions

| Permission | Can |
| --- | --- |
| `pentrix_ops.payments.view` | see payments, invoices (view/download), the daily summary and exports, and the payment widgets |
| `pentrix_ops.payments.manage` | retry synchronisation and reconcile a day |

Candidate, assessment and booking access does not grant payment access, and payment figures on the Overview and the main dashboard are
shown only to people with `payments.view`.
