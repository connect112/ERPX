# Receipt Designer and Generated Receipts (migration 0103)

Where: **Our Internships → an internship → Onboarding Settings → Receipt Designer** (needs the finance management permission to change anything;
the finance view permission is enough to look at the design and the preview) and **Onboarding → Generated receipts** (finance view).

**What it designs.** Presentation only: brand and accent colour, header alignment, logo / signature / stamp, contact line, thank-you and footer
wording, and which optional sections show. The issuer's *legal* identity (legal name, address, GSTIN, number prefix) stays in the internship's
onboarding settings (`config.issuer`, finance permission, versioned) and the amounts, tax lines and numbers come from the verified payment.
A design therefore cannot change what a document legally says. The title, number, issue date, issuer identity, customer name, description,
amounts, tax lines, payment date, transaction reference and payment status are always shown.

**Which layout applies.** Until an administrator explicitly saves a design, documents are issued with the **original layout**, exactly as before
the Receipt Designer existed (the designer's preview shows the new layout, and says so). Once a design is saved, the internship's own design
applies, else the organization's design. Resetting both returns documents to the original layout. Templates are named copies that can be
applied to either. A document records which renderer drew it (`details.render.engine`: `legacy` or `receipt_pdf`) and, for the designer, the
design it used.

**Issuing is unchanged and still one place.** `financial.issue` (called when a payment or refund is confirmed, idempotent per transaction)
draws the PDF with `receipt_pdf.build_receipt_pdf` when a design is saved, and writes the design it used (source, version, the design
itself, the images' checksums) into the document's `details`. If the designer's renderer fails for any reason the document is drawn with the
original layout instead, so a confirmed payment always gets its document. Document numbers, the rules that choose receipt / tax invoice / credit note, the GST split,
emailing and the webhook path are untouched. There is no second ledger: designs only decide how a `FinancialDocument` looks.

**Immutability.** An issued document is never regenerated. Its stored PDF is served byte for byte, and its checksum is verified before it is
served. A database trigger (`trg_internship_financial_documents_immutable`) refuses any UPDATE of a document's number, kind, amount, currency,
parties, details, stored file, checksum or issue time; only the email-delivery fields can change. A correction is a credit note.

**Preview** (`POST .../receipt-designer/preview`) draws in memory from the draft design with sample data or a real confirmed payment. It takes no
document number, stores and emails nothing, writes no event, and marks every page SAMPLE or PREVIEW.

**PDF.** A4, selectable text in embedded DejaVu Sans (the rupee sign is a real glyph), one page for a normal document, more pages (never cut off,
never a page holding only the footer) for a long one.

**API** (all under `/our-internships/{internship_id}`, staff only, organization-scoped):
`GET receipt-designer`, `PUT|DELETE receipt-designer/design`, `POST receipt-designer/preview`,
`POST receipt-designer/assets`, `GET|DELETE receipt-designer/assets/{id}[/image]`,
`POST receipt-designer/templates`, `POST receipt-designer/templates/{id}/apply`, `DELETE receipt-designer/templates/{id}`,
`GET receipts` (search / filters / pages), `GET receipts/{id}/pdf[?download=true]`, `GET receipts/{id}/history`.

**Images** are PNG or JPG up to 2 MB, decoded, shrunk and re-saved as PNG (metadata dropped); SVG and everything else is refused. They are kept
in the database, never under a public URL, and are immutable (a replacement is a new row), so a document can always be traced to the image it used.

**Migration order.** The final sequence is 0101 -> 0102 (onboarding improvements) -> 0103 (this feature). While the onboarding PR is not merged,
0103 branches from 0101 so that this PR builds on its own; **when the onboarding PR is merged, rebase this branch onto master and set 0103's
`down_revision` to `"0102"`** (one line). `tests/unit/test_alembic_single_head.py` fails until that is done, so two heads cannot be merged.

**Rollback.** The tables are new and unused by the previous release, and the guard trigger only forbids changes the previous code never made.
Do not downgrade the database for a code rollback; if the trigger must go, `DROP TRIGGER trg_internship_financial_documents_immutable ON
internship_financial_documents`.
