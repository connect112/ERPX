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
  };
}
