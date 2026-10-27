/** A calendar day (yyyy-mm-dd) as the first instant of that day in the reader's own time zone. */
export function dayStart(day: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d, 0, 0, 0, 0).toISOString();
}

/** A calendar day as the last instant of that day, so access "until 30 Nov" includes the whole of 30 Nov. */
export function dayEnd(day: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d, 23, 59, 59, 999).toISOString();
}

/** An instant back to the yyyy-mm-dd a date box shows (the reader's own time zone); empty for none. */
export function toDay(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export const STATUS: Record<string, { label: string; variant: "success" | "info" | "secondary" }> = {
  active: { label: "Active", variant: "success" },
  upcoming: { label: "Not started", variant: "info" },
  expired: { label: "Ended", variant: "secondary" },
};

function show(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** "From 3 Nov 2026 to 30 Nov 2026", "Until 30 Nov 2026", "From 3 Nov 2026 until removed", or "Until removed". */
export function periodText(from: string | null, until: string | null): string {
  if (from && until) return `${show(from)} to ${show(until)}`;
  if (until) return `Until ${show(until)}`;
  if (from) return `From ${show(from)}, until removed`;
  return "Until removed";
}

/** Whether a chosen start and end day are in a sensible order (either may be empty). */
export function periodOk(from: string, until: string): boolean {
  return !from || !until || until >= from;
}
