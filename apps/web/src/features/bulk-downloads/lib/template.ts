/**
 * Small helpers for the file-name format box. The server is the authority on what a format produces (POST /preview);
 * these only make typing it pleasant: inserting a placeholder at the cursor, and spotting a typo before the round trip.
 */

const PLACEHOLDER = /\{\{\s*([^{}]*?)\s*\}\}/g;

export function placeholderToken(key: string): string {
  return `{{${key}}}`;
}

/** The text with `{{key}}` put where the cursor was (replacing any selected text), and where the cursor goes next. */
export function insertAt(text: string, key: string, start: number | null, end: number | null): { text: string; cursor: number } {
  const token = placeholderToken(key);
  const from = start ?? text.length;
  const to = end ?? from;
  const next = text.slice(0, from) + token + text.slice(to);
  return { text: next, cursor: from + token.length };
}

export function placeholdersIn(text: string): string[] {
  return [...text.matchAll(PLACEHOLDER)].map((m) => m[1]);
}

export function unknownPlaceholders(text: string, known: Iterable<string>): string[] {
  const allowed = new Set(known);
  return [...new Set(placeholdersIn(text).filter((k) => !allowed.has(k)))];
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}
