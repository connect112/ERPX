function show(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** "Access until 30 Nov 2026", or "Access until removed" when the admin set no end. */
export function accessText(until: string | null): string {
  return until ? `Access until ${show(until)}` : "Access until removed";
}
