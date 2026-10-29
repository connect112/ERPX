# Pentrix candidates in ERPX (Phase 3)

The **Pentrix** section of ERPX now has Overview, Registrations and Assessments next to Bookings. They show every candidate who has
registered on the Pentrix portal and where they are in the journey: registration → assessment → qualification → booking → payment.

## Who owns what

Pentrix owns everything. ERPX keeps a *summary* per candidate (`pentrix_candidates`, keyed by the id Pentrix gave them, never matched by
name or email) so lists, filters and dashboards are fast, and asks Pentrix for the full record when someone opens a candidate.
Qualification, payment and booking state are **not worked out in ERPX**: Pentrix reads them from the same services the candidate's own
portal uses (assessment service, payments verified by the provider's webhook, bookings), so the two can never disagree.

## How it stays in step

* **Push (immediate):** Pentrix notices when a candidate, one of their assessment attempts, bookings, payments or programme enrolment is
  saved (`backend/app/services/candidate_tracking.py`, a database-session listener, so no code path can forget) and, after the
  transaction commits, sends the new summary to `POST /api/v1/internal/pentrix/candidates` (signed with the shared secret, best effort).
* **Pull (guarantee):** every minute `pentrix.sync_candidates` asks `GET /api/v1/internal/erpx/candidates?cursor=` for everyone changed
  since a saved cursor (`users.summary_changed_at`, which moves only for changes ERPX shows, not for sign-ins). *Refresh from Pentrix*
  runs it now.
* An older message never overwrites a newer state; the same one twice changes nothing.

## Screens and permissions

| Screen | Permission | Shows |
| --- | --- | --- |
| Overview | `pentrix_ops.overview.view` | totals, journey funnel, payment status, upcoming bookings (needs `bookings.view` too), recent registrations |
| Registrations / one candidate | `pentrix_ops.registrations.view` | the list with filters; registration, assessment, bookings, payments + invoice numbers, emails ERPX sent them, change history |
| Edit name / phone | `pentrix_ops.registrations.manage` | saved **in Pentrix** and recorded there with the ERPX user |
| Assessments / one assessment | `pentrix_ops.assessments.view` | scores and attempts only: no contact details, bookings or payments |

Staff who only take appointments (`pentrix_ops.bookings.assigned`) see none of these.

## Filters

Assessment (not started / in progress / completed / not completed), Qualification (qualified / not qualified / no result yet), Booking
(scheduled / not scheduled / completed / cancelled / no show), Payment (paid / not paid / pending / failed / refunded / none), a
registration date range and a search over name, email and phone. Groups combine with AND, so *Qualified + Not paid + No booking* is
three selections. The filters are in the address bar, so a link opens the list already narrowed. Filtering, sorting and paging run in the
database (25 per page).

"Not qualified" means the candidate **took the assessment and missed the criteria**. Someone who has not been assessed shows "No result yet".

## Pentrix changes

* `users.phone` (optional; the candidate sets it on their Profile page, the ERPX team can edit it) and `users.summary_changed_at`
  (migration `a7b8c9d0e1f2`). Existing people are stamped with their last change so the first pull brings everyone in.
* Internal API additions: `GET /candidates`, `GET /candidates/<id>`, `GET /candidates/<id>/assessment`, `PATCH /candidates/<id>`.

## Not in this phase

Payment records, invoice download, today's collected amount, recent transactions and the daily summary (Phase 4); the bulk
"Send Marketing Email" selection (Phase 5). The Overview therefore shows candidate payment *status* counts only.
