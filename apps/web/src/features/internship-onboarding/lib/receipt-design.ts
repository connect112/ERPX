import type { ReceiptDesign, ReceiptKind, ReceiptSections } from "@/features/internship-onboarding/receipts-api";

/** Parts of the page the designer can switch off, with the words the administrator sees. */
export const OPTIONAL_SECTIONS: { key: keyof ReceiptSections; label: string }[] = [
  { key: "student_email", label: "Student's email address" },
  { key: "student_mobile", label: "Student's mobile number" },
  { key: "application_reference", label: "Application reference" },
  { key: "programme", label: "Internship / programme name" },
  { key: "payment_method", label: "Payment method" },
  { key: "issuer_contacts", label: "Contact details of the issuer" },
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
  const next = typeof current === "object" && current !== null && typeof patch === "object" && patch !== null ? { ...current, ...patch } : patch;
  return { ...design, [key]: next } as ReceiptDesign;
}

export function sameDesign(a: ReceiptDesign, b: ReceiptDesign): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** Where the design in force comes from, in plain words. */
export function sourceLabel(source: "internship" | "organization" | "default"): string {
  return source === "internship" ? "this internship's own design" : source === "organization" ? "the organization's default design" : "the built-in design";
}
