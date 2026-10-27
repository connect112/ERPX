import type { EventStatus, EventType } from "@/features/institutions/api/institutions-api";

export const eventTypeLabels: Record<EventType, string> = {
  workshop: "Workshop",
  hackathon: "Hackathon",
  exam: "Exam",
  other: "Other",
};

export const eventStatusBadge: Record<EventStatus, { label: string; variant: "info" | "success" | "secondary" }> = {
  upcoming: { label: "Upcoming", variant: "info" },
  ongoing: { label: "Ongoing", variant: "success" },
  completed: { label: "Completed", variant: "secondary" },
};

export function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } })?.response
    ?.data?.error;
  const detail = Array.isArray(data?.details) ? data?.details[0]?.msg : undefined;
  return (detail ? detail.replace(/^Value error,\s*/, "") : data?.message) ?? fallback;
}

/** "2026-11-10" -> "10 Nov 2026". Dates are calendar days, so they are never shifted by the reader's time zone. */
export function formatDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function formatDateRange(start: string, end: string): string {
  return start === end ? formatDay(start) : `${formatDay(start)} – ${formatDay(end)}`;
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "";
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
