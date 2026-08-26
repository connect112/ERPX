/**
 * Adzuna's Terms of Service require displaying a "Jobs by Adzuna" credit
 * (min 116x23px) hyperlinked to adzuna.co.uk, using their branding, on any
 * page that shows Adzuna-sourced listings — a real contractual condition of
 * API use, not just courtesy attribution. Rendered in addition to (not
 * instead of) the generic `PostingSourceBadge`, only for
 * `posting.source === "adzuna"`.
 */
export function AdzunaAttribution() {
  return (
    <a
      href="https://www.adzuna.co.uk"
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:underline"
      style={{ minWidth: 116, minHeight: 23 }}
    >
      Jobs by <span className="font-semibold">Adzuna</span>
    </a>
  );
}
