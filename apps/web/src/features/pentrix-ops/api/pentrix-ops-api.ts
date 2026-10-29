import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export type BookingStatus = "requested" | "confirmed" | "in_progress" | "completed" | "cancelled" | "no_show";
export type Scope = "upcoming" | "past" | "all";

export interface PentrixBooking {
  id: string;
  pentrix_booking_id: string;
  reference: string | null;
  candidate_name: string;
  candidate_email: string;
  slot_start: string;
  slot_end: string;
  duration_minutes: number;
  status: BookingStatus;
  status_label: string;
  assigned_staff_user_id: string | null;
  assigned_staff_name: string | null;
  meeting_url: string | null;
  notes: string | null;
  reschedule_count: number;
  cancelled_by: string | null;
  updated_at: string | null;
}

export interface BookingPage {
  items: PentrixBooking[];
  total: number;
  page: number;
  page_size: number;
}

export interface StaffMember {
  id: string;
  full_name: string;
  email: string;
}

export interface BookingFilters {
  scope: Scope;
  status: string;
  staff: string;
  q: string;
  page: number;
  /** Rows per page; the bookings screen uses 20, a dashboard widget fewer. */
  pageSize?: number;
}

export interface Availability {
  timezone: string;
  slot_minutes: number;
  capacity: number;
  dates: { date: string; slots: { start: string; end: string; remaining: number; available: boolean }[] }[];
}

/** The rules Pentrix applies when a candidate books (Pentrix owns them; ERPX only edits them). */
export interface AvailabilitySettings {
  timezone: string;
  working_days: number[];
  start_time: string;
  end_time: string;
  slot_minutes: number;
  capacity: number;
  advance_days: number;
  min_notice_minutes: number;
  available_from: string | null;
  available_until: string | null;
  cancel_cutoff_minutes: number;
  max_reschedules: number;
  meeting_url_template: string;
}

export interface ClosedPeriod {
  id: string;
  start_at: string;
  end_at: string;
  reason: string;
}

const base = "/pentrix-ops";

export const pentrixKeys = {
  all: ["pentrix-ops"] as const,
  bookings: (filters: BookingFilters) => ["pentrix-ops", "bookings", filters] as const,
  mine: (scope: Scope, page: number) => ["pentrix-ops", "mine", scope, page] as const,
  staff: ["pentrix-ops", "staff"] as const,
  settings: ["pentrix-ops", "settings"] as const,
  closed: ["pentrix-ops", "closed"] as const,
  availability: ["pentrix-ops", "availability"] as const,
};

export const pentrixApi = {
  bookings: (f: BookingFilters) =>
    apiClient
      .get<BookingPage>(`${base}/bookings`, {
        params: { scope: f.scope, status: f.status || undefined, staff: f.staff || undefined, q: f.q || undefined, page: f.page, page_size: f.pageSize ?? 20 },
      })
      .then((r) => r.data),
  mine: (scope: Scope, page: number) => apiClient.get<BookingPage>(`${base}/my-bookings`, { params: { scope, page, page_size: 20 } }).then((r) => r.data),
  staff: () => apiClient.get<StaffMember[]>(`${base}/staff`).then((r) => r.data),
  sync: () => apiClient.post<{ updated: number }>(`${base}/sync`).then((r) => r.data),
  assign: (id: string, staffUserId: string | null) => apiClient.post<PentrixBooking>(`${base}/bookings/${id}/assign`, { staff_user_id: staffUserId }).then((r) => r.data),
  setStatus: (id: string, status: string) => apiClient.post<PentrixBooking>(`${base}/bookings/${id}/status`, { status }).then((r) => r.data),
  reschedule: (id: string, slotStart: string) => apiClient.post<PentrixBooking>(`${base}/bookings/${id}/reschedule`, { slot_start: slotStart }).then((r) => r.data),
  cancel: (id: string) => apiClient.post<PentrixBooking>(`${base}/bookings/${id}/cancel`).then((r) => r.data),
  setMeeting: (id: string, url: string | null) => apiClient.put<PentrixBooking>(`${base}/bookings/${id}/meeting`, { meeting_url: url }).then((r) => r.data),
  setNotes: (id: string, notes: string | null) => apiClient.put<PentrixBooking>(`${base}/bookings/${id}/notes`, { notes }).then((r) => r.data),
  availability: () => apiClient.get<Availability>(`${base}/availability`, { params: { days: 21 } }).then((r) => r.data),
  settings: () => apiClient.get<AvailabilitySettings>(`${base}/availability-settings`).then((r) => r.data),
  saveSettings: (changes: Partial<AvailabilitySettings>) => apiClient.put<AvailabilitySettings>(`${base}/availability-settings`, changes).then((r) => r.data),
  closed: () => apiClient.get<ClosedPeriod[]>(`${base}/closed-periods`).then((r) => r.data),
  addClosed: (start_at: string, end_at: string, reason: string) => apiClient.post<ClosedPeriod>(`${base}/closed-periods`, { start_at, end_at, reason }).then((r) => r.data),
  removeClosed: (id: string) => apiClient.delete(`${base}/closed-periods/${id}`).then((r) => r.data),
  // a team member's own appointments
  myStatus: (id: string, status: string) => apiClient.post<PentrixBooking>(`${base}/my-bookings/${id}/status`, { status }).then((r) => r.data),
  myNotes: (id: string, notes: string | null) => apiClient.put<PentrixBooking>(`${base}/my-bookings/${id}/notes`, { notes }).then((r) => r.data),
};

export const useBookings = (filters: BookingFilters) => useQuery({ queryKey: pentrixKeys.bookings(filters), queryFn: () => pentrixApi.bookings(filters), refetchInterval: 60_000 });
export const useMyBookings = (scope: Scope, page: number) => useQuery({ queryKey: pentrixKeys.mine(scope, page), queryFn: () => pentrixApi.mine(scope, page), refetchInterval: 60_000 });
export const useStaff = () => useQuery({ queryKey: pentrixKeys.staff, queryFn: pentrixApi.staff, staleTime: 5 * 60_000 });
