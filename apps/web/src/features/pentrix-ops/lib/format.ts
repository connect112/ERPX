import type { BookingStatus } from "@/features/pentrix-ops/api/pentrix-ops-api";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";

/** Appointments are held in India Standard Time, whatever time zone the person looking at them is in. */
export const IST = "Asia/Kolkata";

export function istDate(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { timeZone: IST, weekday: "short", day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
}

export function istTime(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { timeZone: IST, hour: "numeric", minute: "2-digit", hour12: true }).format(new Date(iso)).toUpperCase();
}

export function istDateTime(iso: string): string {
  return `${istDate(iso)}, ${istTime(iso)} IST`;
}

/** The value for an <input type="datetime-local"> showing this moment in IST. */
export function toIstInput(iso: string): string {
  const parts = new Intl.DateTimeFormat("sv-SE", { timeZone: IST, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
  return parts.replace(" ", "T");
}

/** What a datetime-local value (typed as IST wall-clock time) means as an instant. */
export function fromIstInput(value: string): string {
  return new Date(`${value}:00+05:30`).toISOString();
}

export const STATUS_TONE: Record<BookingStatus, "secondary" | "success" | "warning" | "destructive" | "info"> = {
  requested: "secondary",
  confirmed: "info",
  in_progress: "warning",
  completed: "success",
  cancelled: "destructive",
  no_show: "destructive",
};

export const OPEN_STATUSES: BookingStatus[] = ["requested", "confirmed", "in_progress"];

/** What this person may do with Pentrix appointments. The server checks every one again; this only decides what to show. */
export function usePentrixPermissions() {
  const roles = useMyRoles();
  const data = roles.data;
  const has = (code: string) => !!data && (data.is_superuser || data.effective_permissions.includes(code));
  return {
    loaded: !!data,
    canView: has("pentrix_ops.bookings.view"),
    canManage: has("pentrix_ops.bookings.manage"),
    canTake: has("pentrix_ops.bookings.assigned"),
    canOverview: has("pentrix_ops.overview.view"),
    canRegistrations: has("pentrix_ops.registrations.view"),
    canEditRegistrations: has("pentrix_ops.registrations.manage"),
    canAssessments: has("pentrix_ops.assessments.view"),
    canPayments: has("pentrix_ops.payments.view"),
    canManagePayments: has("pentrix_ops.payments.manage"),
    canMarketing: has("pentrix_ops.marketing.view"),
    canManageMarketing: has("pentrix_ops.marketing.manage"),
    canSendMarketing: has("pentrix_ops.marketing.send"),
  };
}

/** A day in India, e.g. "Tue, 29 Oct 2026". */
export const dayIst = istDate;

export function dayMonthIst(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { timeZone: IST, day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
}

export function agoOrDate(iso: string | null | undefined): string {
  if (!iso) return "Never";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h ago`;
  return dayMonthIst(iso);
}

export function rupees(paise: number, currency = "INR"): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: paise % 100 === 0 ? 0 : 2 }).format(paise / 100);
}

export function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value * 10) / 10}%`;
}

export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const m = Math.floor(seconds / 60);
  return m >= 1 ? `${m} min ${seconds % 60} s` : `${seconds} s`;
}

type Tone = "secondary" | "success" | "warning" | "destructive" | "info";

export const ASSESSMENT_LABEL: Record<string, string> = { not_started: "Not started", in_progress: "In progress", completed: "Completed" };
export const ASSESSMENT_TONE: Record<string, Tone> = { not_started: "secondary", in_progress: "warning", completed: "info" };

/** Qualified / Not qualified / No result yet. A person who has not been assessed is none of the first two. */
export function qualificationOf(qualified: boolean | null): { label: string; tone: Tone } {
  if (qualified === true) return { label: "Qualified", tone: "success" };
  if (qualified === false) return { label: "Not qualified", tone: "destructive" };
  return { label: "No result yet", tone: "secondary" };
}

export const PAYMENT_LABEL: Record<string, string> = { paid: "Paid", pending: "Pending", failed: "Failed", refunded: "Refunded", partially_refunded: "Partially refunded", none: "No payment" };
export const PAYMENT_TONE: Record<string, Tone> = { paid: "success", pending: "warning", failed: "destructive", refunded: "secondary", partially_refunded: "secondary", none: "secondary" };

/** Today's date in India as 2026-10-29, and a date some days away from it. */
export function todayIst(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: IST }).format(new Date());
}

export function addDays(day: string, days: number): string {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** A calendar day such as "2026-10-20" written as "20 Oct 2026". */
export function dayLabel(day: string): string {
  return dayMonthIst(`${day}T12:00:00+05:30`);
}
