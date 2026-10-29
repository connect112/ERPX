# Pentrix bookings in ERPX (Phase 2)

Candidates book one-to-one appointments on the Pentrix portal. ERPX is where the team runs them: assign a team member, change the
booking hours, reschedule, cancel, mark progress, and get reminder emails.

## Who owns what

| | Pentrix (source of truth) | ERPX |
| --- | --- | --- |
| Slots, hours, seats, notice, reschedule/cancel rules, closed periods | yes | edits them through Pentrix |
| A booking and its status, meeting link, notes, assigned team member | yes | a synchronised copy (`pentrix_bookings`) |
| Who the team members are, their permissions | | yes |
| Reminder emails and their wording (Email Studio) | | yes |

Two people can never take the same seat: Pentrix holds each active booking as `(slot_start, slot_seq)` under a unique index.

## How the two stay in step

* **Push:** after every change, Pentrix signs and sends the booking to `POST /api/v1/internal/pentrix/bookings` (best effort; never slows or
  fails the candidate's request).
* **Pull:** every minute `pentrix.sync_bookings` asks Pentrix for everything changed since a saved cursor
  (`GET /api/v1/internal/erpx/bookings?cursor=`). This is what guarantees nothing is missed. *Refresh from Pentrix* on the Bookings screen
  runs it now.
* **Actions from ERPX** (assign, status, reschedule, cancel, meeting link, notes, hours, closed periods) are carried out **in Pentrix**
  through `/api/v1/internal/erpx/...`; Pentrix's answer is written back to the copy. An older message never overwrites a newer state.

Both directions are signed with `ERPX_INTERNAL_SERVICE_SECRET` (the same shared secret as student provisioning). ERPX to Pentrix binds the
method and address into the signature: `HMAC-SHA256(secret, "<ts>.<METHOD>.<path?query>.<body>")` (`X-ERPX-Timestamp`, `X-ERPX-Signature`,
five-minute window; `X-ERPX-Actor` carries the ERPX user for Pentrix's audit trail).

## Configuration (ERPX)

| Variable | Meaning |
| --- | --- |
| `PENTRIX_INTERNAL_API_BASE_URL` | e.g. `http://pentrix_backend:8000` (both stacks are on `webnet`). Empty = the screens say the connection is not configured. |
| `PENTRIX_ORGANIZATION_SLUG` | The organisation whose administrators run Pentrix. `docker-compose.prod.yml` defaults it to `gir-pentrix-program`. Left empty elsewhere, the oldest organisation other than `gir-pentrix-program` is used (right for a development database, wrong for production). |
| `PENTRIX_PORTAL_URL` | Where a candidate reminder links when there is no meeting link yet (default `https://pentrix.in`). |
| `PENTRIX_TIMEZONE` | The zone reminder times are shown in (default `Asia/Kolkata`). |

Pentrix needs `ERPX_INTERNAL_API_BASE_URL` and the same secret (already set for provisioning) so it can push.

## Permissions

| Permission | Can |
| --- | --- |
| `pentrix_ops.bookings.view` | see every appointment and the booking settings |
| `pentrix_ops.bookings.manage` | assign, reschedule, cancel, change status and meeting details, change the booking hours and closed periods |
| `pentrix_ops.bookings.assigned` | see **only their own** assigned appointments; mark them in progress / completed / no show; add notes |

Administrators get all three. The new **Pentrix Staff** system role has only `assigned` (plus the dashboard), so staff do not get Pentrix
administration. Anyone holding `assigned` can be chosen when assigning; an assignment is refused if that person already has an appointment
at an overlapping time.

## Team availability

Pentrix → Booking Settings → **Team availability** lists the team members who can take appointments. *Set hours* gives one or more windows
(a weekday and a start and end time, India time). A member with **no windows is not restricted**: they can be given any appointment the booking hours
allow. A member **with** windows can only be given an appointment that falls completely inside one of them, and ERPX checks this when an appointment
is **assigned** and when an assigned appointment is **moved** (it refuses and names their hours). The existing check against overlapping
appointments still applies. Setting hours needs `pentrix_ops.bookings.manage`; seeing them needs `view`.

## Reminders

Three moments (30 minutes before, 5 minutes before, at the start) to the candidate and the assigned team member, from the Email Studio
templates `pentrix_booking_reminder_<30m|5m|now>_<candidate|staff>` (six, with different wording for each audience; editable and
publishable like any template, category *Pentrix Bookings*).

* Sent by `pentrix.send_booking_reminders` every minute (Celery beat); no browser needs to be open.
* Each send is recorded under a unique key (booking, moment, person, **appointment time**): running twice or overlapping never sends twice.
* A rescheduled appointment gets reminders for its new time only; a cancelled / completed / no-show / already-started one gets none.
* A reminder is sent only within 10 minutes after its moment (a worker that was down does not send "30 minutes to go" late), and only if the
  appointment already existed at that moment (booking ten minutes ahead sends no 30-minute reminder).
* A failed send is retried up to 3 times, then left; the attempts and error are kept on the reminder row.

## Defaults

6:00 PM to 9:00 PM IST, Monday to Friday, one-hour slots, one person per slot, 14 days ahead, at least 60 minutes' notice, change or cancel
until 2 hours before, two reschedules. Everything is editable under *Pentrix → Booking Settings*; nothing is hard-coded in the booking code.

## Not in this phase

Candidate phone numbers were not collected when this phase was built; they are now optional (set by the candidate on their Profile, or by the ERPX
team) and appear on Registrations. The Overview, Registrations, Assessments, Payments and Marketing screens are described in the other
`docs/pentrix-*.md` files.
