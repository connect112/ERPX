import type { CandidateItem, StudentCandidate } from "@/features/institutions/api/institutions-api";

export const STATUS_LABELS: Record<StudentCandidate["status"], { label: string; variant: "info" | "secondary" | "success" }> = {
  new: { label: "New to the institution", variant: "info" },
  at_institution: { label: "Already at the institution", variant: "secondary" },
  registered: { label: "Already on the event", variant: "success" },
};

/** The people who can still be added: not on the event yet and with a usable email. */
export function addable(candidates: Pick<StudentCandidate, "email" | "addable">[]): string[] {
  return candidates.filter((c) => c.addable).map((c) => c.email);
}

/**
 * What to send for the verified people. A name or phone the reviewer corrected is sent; one they left alone is not, so the
 * server keeps what it found. Only emails that are still addable and ticked are included.
 */
export function buildItems(
  candidates: StudentCandidate[],
  verified: Set<string>,
  edits: Record<string, { name?: string; phone?: string }>,
): CandidateItem[] {
  return candidates
    .filter((c) => c.addable && verified.has(c.email))
    .map((c) => {
      const edit = edits[c.email] ?? {};
      const name = edit.name?.trim();
      const phone = edit.phone?.trim();
      return { email: c.email, name: name && name !== c.name ? name : null, phone: phone !== undefined && phone !== (c.phone ?? "") ? phone || null : null };
    });
}

/** A short line saying where a person was found, e.g. "Exam: Day 1 MCQ · Hackathon: DevSecStorm". */
export function sourceLine(sources: StudentCandidate["sources"]): string {
  return sources.map((s) => `${s.kind === "exam" ? "Exam" : "Hackathon"}: ${s.title}`).join(" · ");
}
