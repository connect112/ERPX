import type { OfferField, OfferFieldKey } from "@/features/our-internships/api/our-internships-api";

/** The order the details are listed in, and the sample text shown where each one is placed. */
export const FIELD_ORDER: OfferFieldKey[] = ["name", "institution", "internship", "date", "reference"];

export const SAMPLE_TEXT: Record<OfferFieldKey, string> = {
  name: "Asha Rao",
  institution: "Sri Venkateswara College",
  internship: "Pentrix Cyber Internship",
  date: "27 October 2026",
  reference: "OFR-2026-AB12-001",
};

/** Sensible starting looks: the student's name big, bold and centred; everything else a small left-aligned line. */
export function defaultField(key: OfferFieldKey, page: number, x: number, y: number): OfferField {
  const base = { key, page, x, y, color: "#111827" };
  if (key === "name") return { ...base, font: "sans_bold", font_size: 0.03, max_width: 0.6, align: "center" };
  return { ...base, font: "sans", font_size: 0.018, max_width: 0.4, align: "left" };
}

export const clamp01 = (value: number): number => Math.min(1, Math.max(0, value));

/** Where a click landed on the page, as fractions of its width and height (clamped to the page). */
export function fractionFromClick(rect: { left: number; top: number; width: number; height: number }, clientX: number, clientY: number) {
  if (rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 };
  return { x: clamp01((clientX - rect.left) / rect.width), y: clamp01((clientY - rect.top) / rect.height) };
}

/** Place a detail (or move it, keeping its look) at a point on a page. */
export function placeField(fields: OfferField[], key: OfferFieldKey, page: number, x: number, y: number): OfferField[] {
  const existing = fields.find((f) => f.key === key);
  const next = existing ? { ...existing, page, x: round(x), y: round(y) } : defaultField(key, page, round(x), round(y));
  return sortFields(existing ? fields.map((f) => (f.key === key ? next : f)) : [...fields, next]);
}

/** Move a placed detail by a small amount (the arrow keys), staying on the page. A detail not placed yet does not move. */
export function nudgeField(fields: OfferField[], key: OfferFieldKey, dx: number, dy: number): OfferField[] {
  return fields.map((f) => (f.key === key ? { ...f, x: round(f.x + dx), y: round(f.y + dy) } : f));
}

export function updateField(fields: OfferField[], key: OfferFieldKey, change: Partial<OfferField>): OfferField[] {
  return fields.map((f) => (f.key === key ? { ...f, ...change } : f));
}

export function removeField(fields: OfferField[], key: OfferFieldKey): OfferField[] {
  return fields.filter((f) => f.key !== key);
}

export function sortFields(fields: OfferField[]): OfferField[] {
  return [...fields].sort((a, b) => FIELD_ORDER.indexOf(a.key) - FIELD_ORDER.indexOf(b.key));
}

/** The server needs the student's name placed; the rest are optional. */
export function layoutProblem(fields: OfferField[]): string | null {
  if (fields.length > 0 && !fields.some((f) => f.key === "name")) return "Place the student's name on the letter.";
  return null;
}

/** Whether the unsaved layout differs from the saved one. */
export function sameLayout(a: OfferField[], b: OfferField[]): boolean {
  return JSON.stringify(sortFields(a)) === JSON.stringify(sortFields(b));
}

/** Drop fields on pages the letter does not have (after a shorter template replaced a longer one). */
export function withinPages(fields: OfferField[], pages: number): OfferField[] {
  return fields.filter((f) => f.page <= pages);
}

const round = (value: number): number => Math.round(clamp01(value) * 10000) / 10000;

/** CSS font stack for the on-screen sample of a PDF font, which only approximates it. */
export function cssFont(font: OfferField["font"]): { fontFamily: string; fontWeight: number } {
  const serif = font.startsWith("serif");
  return {
    fontFamily: serif ? "'Times New Roman', Times, serif" : "Helvetica, Arial, sans-serif",
    fontWeight: font.endsWith("bold") ? 700 : 400,
  };
}
