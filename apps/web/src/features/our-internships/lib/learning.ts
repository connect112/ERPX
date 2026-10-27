import type { AssignmentStatus, ExamResultRow, RubricRule } from "@/features/our-internships/api/learning-api";

/** An ISO instant -> the value a <input type="datetime-local"> shows (the reader's own time zone). */
export function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** A <input type="datetime-local"> value -> an ISO instant (null when empty or unreadable). */
export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function rubricTotal(rubric: Pick<RubricRule, "points">[]): number {
  return rubric.reduce((sum, rule) => sum + (Number.isFinite(rule.points) ? rule.points : 0), 0);
}

/** The marks a set of per-criterion entries add up to; blanks count as zero. */
export function sumScores(scores: Record<string, string>): number {
  return Math.round(Object.values(scores).reduce((sum, v) => sum + (Number(v) || 0), 0) * 100) / 100;
}

export const ASSIGNMENT_STATUS: Record<AssignmentStatus, { label: string; variant: "secondary" | "success" | "warning" }> = {
  draft: { label: "Draft", variant: "secondary" },
  published: { label: "Published", variant: "success" },
  closed: { label: "Closed", variant: "warning" },
};

export const EXAM_STATE_LABELS: Record<ExamResultRow["state"], string> = {
  not_assigned: "Not assigned",
  not_started: "Not started",
  in_progress: "In progress",
  submitted: "Submitted",
};

/** Whether the deadline has passed (no deadline never passes). */
export function isPastDeadline(deadline: string | null, now: Date = new Date()): boolean {
  return !!deadline && new Date(deadline).getTime() < now.getTime();
}

/** A stable short id for a new task or rubric row. */
export function newRowId(prefix: string, existing: string[]): string {
  let n = existing.length + 1;
  while (existing.includes(`${prefix}${n}`)) n += 1;
  return `${prefix}${n}`;
}
