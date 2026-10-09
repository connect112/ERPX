import type { PostStatus, VerificationStatus } from "@/features/social-media/api/social-media-api";

export const STATUS_LABEL: Record<PostStatus, string> = {
  draft: "Draft",
  review: "In review",
  approved: "Approved",
  scheduled: "Scheduled",
  publishing: "Publishing",
  published: "Published",
  failed: "Failed",
  cancelled: "Cancelled",
  publish_unknown: "Outcome unclear",
};

export const STATUS_VARIANT: Record<PostStatus, "default" | "secondary" | "success" | "warning" | "info" | "destructive" | "outline"> = {
  draft: "secondary",
  review: "info",
  approved: "success",
  scheduled: "info",
  publishing: "info",
  published: "success",
  failed: "destructive",
  cancelled: "outline",
  publish_unknown: "warning",
};

export const VERIFICATION_LABEL: Record<VerificationStatus, string> = {
  not_required: "No factual claims",
  unverified: "Not verified yet",
  verified: "Verified against sources",
  conflicting: "Sources conflict",
  outdated: "Outdated",
};

export const FORMAT_LABEL = { image: "Single image", carousel: "Carousel", reel: "Reel", story: "Story" } as const;

export const TIMEZONES = [
  "Asia/Kolkata",
  "UTC",
  "Asia/Dubai",
  "Asia/Singapore",
  "Europe/London",
  "America/New_York",
  "America/Los_Angeles",
  "Australia/Sydney",
];

export function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } })?.response?.data?.error;
  const detail = Array.isArray(data?.details) ? data?.details[0]?.msg : undefined;
  return (detail ? detail.replace(/^Value error,\s*/, "") : data?.message) ?? fallback;
}

/** "2026-11-01T09:00:00+05:30" -> the value a datetime-local input wants, in the browser's own zone is NOT what we want:
 * the schedule is in the account timezone, so the time is sent without an offset and the server applies that zone. */
export function toInputValue(iso: string | null, timeZone: string): string {
  if (!iso) return "";
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
  return parts.replace(" ", "T");
}

export function formatInZone(iso: string | null, timeZone: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("en-IN", { timeZone, dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}
