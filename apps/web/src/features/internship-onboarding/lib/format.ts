/** Display helpers for onboarding. Amounts arrive as decimal strings and are never turned into floats for maths. */

export const STATUS_LABELS: Record<string, string> = {
  not_issued: "Not issued",
  delivery_pending: "Sending",
  delivery_failed: "Delivery failed",
  awaiting_response: "Awaiting response",
  accepted: "Accepted",
  declined: "Declined",
  expired: "Expired",
  not_required: "Not required",
  not_submitted: "Not submitted",
  partially_submitted: "Partly submitted",
  submitted: "Submitted",
  under_review: "Under review",
  changes_requested: "Changes requested",
  verified: "Verified",
  rejected: "Rejected",
  not_initiated: "Not started",
  pending: "Pending",
  awaiting_manual_verification: "Awaiting verification",
  paid: "Paid",
  failed: "Failed",
  partially_paid: "Part paid",
  refunded: "Refunded",
  partially_refunded: "Part refunded",
  not_started: "Not started",
  in_progress: "In progress",
  awaiting_acceptance: "Awaiting acceptance",
  awaiting_documents: "Awaiting documents",
  awaiting_verification: "Awaiting verification",
  awaiting_payment: "Awaiting payment",
  awaiting_manual_payment_approval: "Payment being checked",
  completed: "Completed",
  cancelled: "Cancelled",
  granted: "Granted",
  not_granted: "Not granted",
  revoked: "Revoked",
};

export function statusLabel(value: string): string {
  return STATUS_LABELS[value] ?? value.replace(/_/g, " ");
}

export function statusTone(value: string): "success" | "warning" | "destructive" | "info" | "secondary" {
  if (["completed", "paid", "verified", "accepted", "granted", "not_required"].includes(value)) return "success";
  if (["declined", "rejected", "failed", "expired", "cancelled", "delivery_failed", "changes_requested"].includes(value)) return "destructive";
  if (value.startsWith("awaiting") || ["submitted", "under_review", "pending", "partially_paid", "partially_submitted"].includes(value)) return "warning";
  if (["in_progress", "awaiting_response"].includes(value)) return "info";
  return "secondary";
}

/** "5000.00" + "INR" -> "₹5,000.00" without floating-point maths on the stored value. */
export function money(amount: string | null | undefined, currency = "INR"): string {
  if (amount == null || amount === "") return "—";
  const [whole, fraction = "00"] = amount.replace(/^-/, "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const symbol = currency === "INR" ? "₹" : `${currency} `;
  return `${amount.startsWith("-") ? "-" : ""}${symbol}${grouped}.${fraction.padEnd(2, "0").slice(0, 2)}`;
}

/** An ISO time shown in the internship's own time zone, so everybody sees the same deadline. */
export function inZone(iso: string | null | undefined, timeZone: string): string {
  if (!iso) return "—";
  try {
    // explicit parts: Intl refuses timeZoneName together with dateStyle/timeStyle
    return new Intl.DateTimeFormat("en-IN", {
      day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", timeZone, timeZoneName: "short",
    }).format(new Date(iso));
  } catch {
    return new Date(iso).toLocaleString();
  }
}

/** <input type="datetime-local"> value <-> ISO with the browser's offset (the server stores it unambiguously). */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

/** The token from the link's fragment (#t=...). It is never sent to a server in a URL. */
export function tokenFromHash(hash: string): string | null {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const t = params.get("t");
  return t && /^[A-Za-z0-9_-]{20,200}$/.test(t) ? t : null;
}

export function slugKey(label: string, taken: Set<string>): string {
  let base = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 36) || "field";
  if (!/^[a-z]/.test(base)) base = `f_${base}`;
  let key = base;
  let n = 2;
  while (taken.has(key)) key = `${base}_${n++}`;
  return key;
}
