import type { SelectedStudent } from "@/features/our-internships/api/our-internships-api";

export type BadgeVariant = "secondary" | "info" | "success" | "warning" | "destructive" | "outline";

/** The look of each stage a selected student can be in (the server decides which stage they are in). */
export const stageBadge: Record<string, BadgeVariant> = {
  selected: "secondary",
  offer_sent: "info",
  accepted: "info",
  verified: "warning",
  paid: "warning",
  ready_for_lms: "warning",
  lms_access: "success",
  declined: "destructive",
  rejected: "destructive",
};

/** The stages in the order a student normally moves through them, for the summary strip. */
export const STAGE_ORDER = ["selected", "offer_sent", "accepted", "verified", "paid", "ready_for_lms", "lms_access", "declined", "rejected"] as const;

export function stageVariant(stage: string): BadgeVariant {
  return stageBadge[stage] ?? "secondary";
}

/** How many students are in each stage. */
export function stageCounts(items: SelectedStudent[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const item of items) counts[item.stage] = (counts[item.stage] ?? 0) + 1;
  return counts;
}

/** Students who can be given LMS access right now: verified and paid, course chosen, not declined, not already granted. */
export function grantableIds(items: SelectedStudent[]): string[] {
  return items.filter((i) => i.lms_status !== "granted" && i.grant_blockers.length === 0).map((i) => i.student_id);
}

/** The blockers worth showing: "already granted" is a state, not a problem. */
export function visibleBlockers(item: SelectedStudent): string[] {
  return item.lms_status === "granted" ? [] : item.grant_blockers;
}

/** Split ids into batches (the server grants at most this many per request). */
export function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

export const OFFER_RESPONSE_LABELS = { awaiting: "No reply yet", accepted: "Accepted", declined: "Declined" } as const;
export const VERIFICATION_LABELS = { pending: "Pending", verified: "Verified", rejected: "Failed" } as const;
export const PAYMENT_LABELS = { pending: "Not received", paid: "Received" } as const;
export const LMS_LABELS = { not_granted: "No access", granted: "Access granted", revoked: "Access withdrawn" } as const;

/** A payment amount as text for an input; empty when there is none. */
export function amountText(amount: number | null): string {
  return amount === null ? "" : String(amount);
}

/** Text from an amount box back to a number: empty is "no amount", anything unreadable or negative is rejected (undefined). */
export function parseAmount(text: string): number | null | undefined {
  const t = text.trim();
  if (t === "") return null;
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return undefined;
  return Number(t);
}
