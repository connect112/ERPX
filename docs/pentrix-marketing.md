# Pentrix marketing email in ERPX (Phase 5)

Pentrix → **Registrations** lets an administrator pick candidates and send them a marketing email built in **Email Studio**. Pentrix →
**Marketing** says which Email Studio templates may be used (and when) and tracks what was sent.

There is no second email builder and no second sender: designs, wording, brand profiles and signatures are Email Studio's; delivery is
ERPX's existing email service (`packages/email`).

## Who may be emailed

A candidate is emailed **only if all of these hold**:

1. They **agreed to marketing email** in Pentrix. This is an explicit, optional, unticked box at sign-up (password and Google sign-up) and a
   toggle in portal **Settings**. Accepting the Terms never counts as agreeing, and existing candidates are *not* opted in.
2. Their email address is verified.
3. They have not unsubscribed.
4. Their address is not already in the same selection (no duplicates).
5. They have not been sent **the same template** in the last 30 days.

The same rules are applied again **at the moment each message is sent**, so someone who turns marketing off after a send was confirmed does
not get it. Recipients that are left out are counted with the reason, in the Recipients step and on the campaign.

Booking confirmations and reminders, payment emails and account emails are transactional: they use their own templates and code paths, never
look at this choice, and never carry a marketing footer.

## The five steps (Registrations → Send Marketing Email)

Select candidates one by one (ticks persist across pages), or **Select all N matching these filters** (and untick anyone). Then:

1. **Recipients**: how many were selected, how many can be emailed, who was left out and why, and the first 50 addresses.
2. **Template**: published templates made available for Pentrix marketing, inside their dates. Search, filter by category or by campaign date.
3. **Preview template**: the design with sample candidate details, in a sandboxed frame.
4. **Final preview**: subject, resolved content, brand profile and signature (changeable), attachments, recipient count, and *preview as* any
   recipient.
5. **Confirm and send**: an explicit tick, then **Send to N people**. The server re-chooses the people and refuses if the number is not the
   one shown ("review again"). The confirmation carries a one-time key, so a double click or a retry makes one campaign.

## Templates and their dates

Pentrix → Marketing → *Make a template available*: pick a **published** Email Studio template, name the **campaign**, optionally set
*available from / until*, switch on or off. Last-updated date and category come from the template. Templates that need a per-recipient
document (an offer letter) cannot be marketing emails. Create the category **Pentrix Marketing** templates in Email Studio; the placeholders
available are `first_name`, `full_name`, `email`, `campaign_name`, `assessment_status`, `qualification_status`, `portal_url`, `unsubscribe_url`.

## Unsubscribing

Every message carries a signed **unsubscribe link** (a page that needs no sign-in) and `List-Unsubscribe` / one-click headers, whether or
not the template's author included one. An unsubscribe is honoured **at once** in ERPX (a suppression for that address), waiting messages
are dropped, and Pentrix is then told so the candidate's Settings show it too (retried every minute until it is). The links do not expire.
A suppression is lifted only if the candidate later **opts in again themselves**; ERPX can only ever turn consent off, never on.

## Sending, rate limits and tracking

* `pentrix.dispatch_marketing` runs every minute and sends at most `PENTRIX_MARKETING_PER_MINUTE` (default 60) messages across all
  campaigns. A campaign is at most 5,000 people; one person may start 20 sends an hour.
* The database refuses the same address twice in a campaign. Each message is claimed before it is sent; a worker that dies mid-batch has
  its claims returned after 10 minutes, and a message already recorded as sent is never sent again. A refused message is retried up to 3 times.
* **Tracking:** queued, sending, sent, failed and skipped are recorded per recipient. **Delivered and bounced stay at 0**: they need delivery
  reports from the mail provider, which ERPX does not receive over SMTP. A campaign can be cancelled; what has gone cannot be recalled.

## Permissions

| Permission | Can |
| --- | --- |
| `pentrix_ops.marketing.view` | see the templates made available and the campaigns sent |
| `pentrix_ops.marketing.manage` | make templates available, set their dates, switch them off or remove them |
| `pentrix_ops.marketing.send` | choose recipients, preview and confirm a send, cancel one |

## Pentrix changes

`users.marketing_opt_in` / `marketing_opt_in_at` (migration `c9d0e1f2a3b4`; everyone starts off), the sign-up and Google sign-up boxes,
the Settings toggle, `POST /api/v1/internal/erpx/candidates/<id>/marketing-unsubscribe` (turn-off only), and the choice in the candidate
summary ERPX synchronises. The Privacy Policy text has not been changed; it should mention marketing consent and the unsubscribe right.
