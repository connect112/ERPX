import type { InternshipStatus, StudentPerformance } from "@/features/our-internships/api/our-internships-api";

export type SortKey = "name" | "team_score" | "individual" | "exam";
export type SortDirection = "asc" | "desc";

export const statusBadge: Record<InternshipStatus, { label: string; variant: "info" | "success" | "secondary" }> = {
  selecting: { label: "Selecting students", variant: "info" },
  offers_released: { label: "Offers released", variant: "success" },
  closed: { label: "Closed", variant: "secondary" },
};

/** "8 / 10 (80%)" for marks, "—" when there are none (did not sit, or no exam). */
export function formatMarks(score: number | null, total: number | null, percent?: number | null): string {
  if (score === null) return "—";
  if (!total) return String(score);
  return percent !== null && percent !== undefined ? `${score} / ${total} (${percent}%)` : `${score} / ${total}`;
}

/** "80 / 100 · #1" for a team's hackathon score, "—" when it has not been scored. */
export function formatTeamScore(score: number | null, max: number | null, rank: number | null): string {
  if (score === null) return "—";
  const base = max ? `${score} / ${max}` : String(score);
  return rank ? `${base} · #${rank}` : base;
}

export function formatScore(score: number | null): string {
  return score === null ? "—" : String(score);
}

function valueFor(row: StudentPerformance, key: SortKey): number | string | null {
  switch (key) {
    case "name":
      return row.name.toLowerCase();
    case "team_score":
      return row.team && row.team.tasks_scored > 0 ? row.team.score : null;
    case "individual":
      return row.individual_score;
    case "exam":
      return row.exam_percent;
  }
}

/**
 * Sort for choosing: people with no value for the column (did not sit the exam, not in a scored team) always go last,
 * whichever way the column is sorted, so "best first" is never a screen of blanks.
 */
export function sortStudents(rows: StudentPerformance[], key: SortKey, direction: SortDirection): StudentPerformance[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = valueFor(a, key);
    const y = valueFor(b, key);
    if (x === null && y === null) return a.name.localeCompare(b.name);
    if (x === null) return 1;
    if (y === null) return -1;
    if (x < y) return -sign;
    if (x > y) return sign;
    return a.name.localeCompare(b.name);
  });
}

/** What can still be added: rows not already selected, one per person even if they appear in several events. */
export function selectableIds(rows: StudentPerformance[]): string[] {
  return [...new Set(rows.filter((r) => !r.selected).map((r) => r.student_id))];
}
