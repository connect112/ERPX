/** The seven Learning tabs, in order (the server sends the same list; this is for reading old links and for tests). */
export const LEARNING_TABS = ["curriculum", "enrollments", "evaluations", "projects", "discussions", "practicals", "viva"] as const;

/** Links made before the Learning workspace: the three evaluation tabs of a course, and an internship's exams, assignments and projects. */
const LEGACY: Record<string, string> = { assignments: "evaluations", assessments: "evaluations", exams: "evaluations" };

/** The Learning tab a `?tab=` value stands for, or null when it is not a learning tab. */
export function learningTabFromParam(value: string | null): string | null {
  if (!value) return null;
  const mapped = LEGACY[value] ?? value;
  return (LEARNING_TABS as readonly string[]).includes(mapped) ? mapped : null;
}
