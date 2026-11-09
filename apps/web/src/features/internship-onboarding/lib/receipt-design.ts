import type { BodyPart, ReceiptDesign, ReceiptKind, ReceiptLabels, ReceiptSections, SampleData } from "@/features/internship-onboarding/receipts-api";

/** Parts of the page the designer can switch off, with the words the administrator sees. */
export const OPTIONAL_SECTIONS: { key: keyof ReceiptSections; label: string }[] = [
  { key: "student_email", label: "Student's email address" },
  { key: "student_mobile", label: "Student's mobile number" },
  { key: "application_reference", label: "Application reference" },
  { key: "programme", label: "Internship / programme name" },
  { key: "payment_method", label: "Payment method" },
  { key: "issuer_contacts", label: "Contact details of the issuer" },
  { key: "issuer_address", label: "Issuer's address (the GSTIN always shows when there is one)" },
  { key: "thank_you", label: "Thank-you message (not on credit notes)" },
  { key: "footer", label: "Footer text" },
];

/** What is always on the document: it is what makes it a financial document, so it cannot be hidden. */
export const MANDATORY_PARTS = [
  "Document title, number and issue date",
  "Issuer's legal name, address and GSTIN",
  "Customer name",
  "Description, amount, tax lines and total",
  "Payment date, transaction reference and payment status",
];

export const KIND_LABELS: Record<ReceiptKind, string> = { receipt: "Payment receipt", tax_invoice: "Tax invoice", credit_note: "Credit note" };

export const HEX = /^#[0-9a-fA-F]{6}$/;

function luminance(hex: string): number {
  const channel = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** Contrast of a colour against white (the server refuses a brand colour below 3). */
export function contrastWithWhite(hex: string): number {
  return 1.05 / (luminance(hex) + 0.05);
}

/** What is wrong with the brand colour, in words, or null. The server checks again. */
export function brandColorProblem(hex: string): string | null {
  if (!HEX.test(hex)) return "Use a colour like #1F3A5F.";
  if (contrastWithWhite(hex) < 3) return "That colour is too light to read on a white page. Choose a darker one.";
  return null;
}

/** A copy with one part changed (designs are small, plain data). */
export function withPatch<K extends keyof ReceiptDesign>(design: ReceiptDesign, key: K, patch: Partial<ReceiptDesign[K]> | ReceiptDesign[K]): ReceiptDesign {
  const current = design[key];
  const mergeable = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v); // a list (the section order) is replaced, never merged
  const next = mergeable(current) && mergeable(patch) ? { ...(current as object), ...(patch as object) } : patch;
  return { ...design, [key]: next } as ReceiptDesign;
}

export function sameDesign(a: ReceiptDesign, b: ReceiptDesign): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** Where the design in force comes from, in plain words. */
export function sourceLabel(source: "internship" | "organization" | "default"): string {
  return source === "internship" ? "this internship's own design" : source === "organization" ? "the organization's default design" : "the built-in design";
}

/** Every word that can be changed, with the plain-language name shown to the administrator. */
export const LABEL_FIELDS: Record<keyof ReceiptLabels, { label: string; max: number; hint?: string }> = {
  title_receipt: { label: "Receipt title", max: 40, hint: "Cannot say invoice or credit note." },
  title_tax_invoice: { label: "Tax invoice title", max: 40, hint: 'Must contain "Tax Invoice".' },
  title_credit_note: { label: "Credit note title", max: 40, hint: 'Must contain "Credit Note".' },
  subtitle_receipt: { label: "Receipt subtitle", max: 120 },
  subtitle_tax_invoice: { label: "Tax invoice subtitle", max: 120 },
  subtitle_credit_note: { label: "Credit note subtitle", max: 120 },
  number: { label: "Before the document number", max: 20 },
  issue_date: { label: "Before the issue date", max: 20 },
  gstin: { label: "Before the GSTIN", max: 20 },
  mobile: { label: "Before the mobile number", max: 20 },
  billed_to: { label: "Customer heading", max: 30 },
  payment_details: { label: "Payment details heading", max: 30 },
  application: { label: "Application reference label", max: 30 },
  programme: { label: "Programme label", max: 30 },
  payment_method: { label: "Payment method label", max: 30 },
  transaction_ref: { label: "Transaction reference label", max: 30 },
  payment_date: { label: "Payment date label", max: 30 },
  against: { label: "Credit note: original document label", max: 30 },
  payment_status: { label: "Payment status label", max: 30 },
  col_description: { label: "Table heading: description", max: 30 },
  col_amount: { label: "Table heading: amount", max: 30 },
  total_received: { label: "Total line (receipt, tax invoice)", max: 40 },
  total_refunded: { label: "Total line (credit note)", max: 40 },
  status_paid: { label: "Badge for a payment", max: 20, hint: "Cannot say refunded." },
  status_refunded: { label: "Badge for a refund", max: 20, hint: "Cannot say paid." },
  status_paid_word: { label: "Status wording for a payment", max: 20 },
  status_refunded_word: { label: "Status wording for a refund", max: 20 },
  system_line: { label: "Note when there is no signature", max: 200 },
  page: { label: "Word before the page number", max: 20 },
};

export const LABEL_GROUPS: { title: string; hint?: string; keys: (keyof ReceiptLabels)[] }[] = [
  { title: "Numbers and dates", keys: ["number", "issue_date", "gstin", "mobile"] },
  { title: "Customer and payment details", keys: ["billed_to", "payment_details", "application", "programme", "payment_method", "transaction_ref", "payment_date", "against", "payment_status"] },
  { title: "Table and totals", keys: ["col_description", "col_amount", "total_received", "total_refunded"] },
  { title: "Status wording", keys: ["status_paid", "status_refunded", "status_paid_word", "status_refunded_word"] },
  { title: "Notes and page numbers", keys: ["system_line", "page"] },
];

export const KIND_TITLE_KEYS: Record<ReceiptKind, { title: keyof ReceiptLabels; subtitle: keyof ReceiptLabels }> = {
  receipt: { title: "title_receipt", subtitle: "subtitle_receipt" },
  tax_invoice: { title: "title_tax_invoice", subtitle: "subtitle_tax_invoice" },
  credit_note: { title: "title_credit_note", subtitle: "subtitle_credit_note" },
};

export const BODY_PART_LABELS: Record<BodyPart, string> = {
  details: "Customer and payment details",
  items: "Description, amounts and total",
  thank_you: "Thank-you message",
  signature: "Signature, stamp and note",
};

/** What is wrong with a title, in words (the server checks again): a title may be reworded but never say it is another kind of document. */
export function titleProblem(kind: ReceiptKind, title: string): string | null {
  const t = title.toLowerCase();
  if (!title.trim()) return "Enter a title.";
  if (kind === "tax_invoice" && (!t.includes("tax invoice") || t.includes("credit note"))) return 'A tax invoice title must contain "Tax Invoice".';
  if (kind === "credit_note" && (!t.includes("credit note") || t.includes("invoice"))) return 'A credit note title must contain "Credit Note".';
  if (kind === "receipt" && (t.includes("invoice") || t.includes("credit note"))) return "A receipt title cannot call the document an invoice or a credit note.";
  return null;
}

/** The sample values that are filled in (empty ones are left out so the preview keeps its own sample). */
export function sampleBody(sample: Record<string, string>): SampleData | undefined {
  const filled = Object.fromEntries(Object.entries(sample).filter(([, v]) => v.trim() !== ""));
  return Object.keys(filled).length ? (filled as SampleData) : undefined;
}

/** Moves a part of the body up (-1) or down (1). */
export function movePart(order: BodyPart[], part: BodyPart, by: -1 | 1): BodyPart[] {
  const i = order.indexOf(part);
  const j = i + by;
  if (i < 0 || j < 0 || j >= order.length) return order;
  const next = [...order];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}
