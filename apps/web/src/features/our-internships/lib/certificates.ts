import type { CertificateKind, Delivery, EligibilityRow } from "@/features/our-internships/api/certificates-api";

export const KIND_LABELS: Record<CertificateKind, string> = { participation: "Participation", completion: "Completion" };

export const DELIVERY: Record<Delivery, { label: string; variant: "secondary" | "warning" | "info" | "success" }> = {
  not_selected: { label: "Not selected", variant: "secondary" },
  not_created: { label: "Not released yet", variant: "secondary" },
  held_for_review: { label: "Waiting for review", variant: "warning" },
  queued: { label: "Email not delivered yet", variant: "info" },
  sent: { label: "Sent", variant: "success" },
};

/** Per kind, how many students are eligible. A student is on one list only, so the two never add up to more than the students. */
export function countsByKind(rows: Pick<EligibilityRow, "kind">[]): Record<CertificateKind, number> {
  return {
    participation: rows.filter((r) => r.kind === "participation").length,
    completion: rows.filter((r) => r.kind === "completion").length,
  };
}

/** The students a bulk choice can still change: a student whose certificate already exists is fixed. */
export function changeable(rows: Pick<EligibilityRow, "selection_id" | "locked">[], picked: Set<string>): string[] {
  return rows.filter((r) => picked.has(r.selection_id) && !r.locked).map((r) => r.selection_id);
}

/** What happens to the certificates when released, in a sentence. */
export function releaseSummary(plans: { label: string; will_send: number; already_sent: number }[]): string {
  const parts = plans.map((p) => `${p.will_send} ${p.label.toLowerCase()}${p.already_sent ? ` (${p.already_sent} already sent)` : ""}`);
  return parts.length ? parts.join(", ") : "Nothing to send";
}
