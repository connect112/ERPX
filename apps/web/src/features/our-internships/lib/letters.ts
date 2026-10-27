import type { LetterConfig, RowStatus } from "@/features/our-internships/api/letters-api";

export const ROW_STATUS: Record<RowStatus, { label: string; variant: "success" | "info" | "secondary" | "destructive" | "warning" | "outline" }> = {
  missing_data: { label: "Missing data", variant: "warning" },
  not_generated: { label: "Not generated", variant: "outline" },
  pending: { label: "Pending", variant: "secondary" },
  generating: { label: "Generating", variant: "info" },
  ready: { label: "Ready", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  approved: { label: "Approved", variant: "info" },
  released: { label: "Released", variant: "success" },
};

export const DESIGN_TEXT = {
  not_approved: "The design has not been approved yet.",
  approved: "The design is approved.",
  changed: "The settings changed after the design was approved. Preview and approve it again.",
} as const;

export const REASONS = [
  { value: "hackathon", label: "Hackathon performance" },
  { value: "workshop", label: "Workshop performance" },
  { value: "technical_evaluation", label: "Technical evaluation" },
  { value: "direct_selection", label: "Direct selection" },
  { value: "custom", label: "Custom reason" },
] as const;

/** A list with one entry replaced. */
export function replaceAt<T>(items: T[], index: number, value: T): T[] {
  return items.map((item, i) => (i === index ? value : item));
}

export function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_, i) => i !== index);
}

/** A list with the entry at ``index`` moved by ``by`` places (-1 up, 1 down); unchanged when it would leave the list. */
export function moveBy<T>(items: T[], index: number, by: -1 | 1): T[] {
  const target = index + by;
  if (index < 0 || index >= items.length || target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** True when two settings differ, so the Save button knows there is something to save. */
export function configChanged(a: LetterConfig | null, b: LetterConfig | null): boolean {
  return JSON.stringify(a) !== JSON.stringify(b);
}

/** A copy of the settings with the value at a path (``["branding", "logo", "show"]``) replaced. */
export function setPath<T extends object>(obj: T, path: (string | number)[], value: unknown): T {
  if (path.length === 0) return value as T;
  const [head, ...rest] = path;
  const copy = (Array.isArray(obj) ? [...obj] : { ...obj }) as Record<string | number, unknown>;
  copy[head] = setPath((copy[head] ?? {}) as object, rest, value);
  return copy as T;
}

export function safeFileName(name: string): string {
  return name.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "file";
}

/** Open a PDF in a new tab. */
export function openBlob(blob: Blob, type = "application/pdf") {
  const url = URL.createObjectURL(new Blob([blob], { type }));
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Save a file the browser has downloaded. */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
