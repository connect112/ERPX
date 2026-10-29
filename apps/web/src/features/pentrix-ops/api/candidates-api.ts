import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

const base = "/pentrix-ops";

export type AssessmentState = "not_started" | "in_progress" | "completed";
export type PaymentState = "paid" | "pending" | "failed" | "refunded" | "none";

export interface AssessmentLine {
  state: AssessmentState;
  attempts: number;
  readiness_commitment_pct: number | null;
  technical_pct: number | null;
  /** null until there is a submitted result: "not qualified" only ever means the candidate tried and missed the criteria. */
  qualified: boolean | null;
  assessed_at: string | null;
}

export interface BookingLine {
  status: string;
  status_label: string;
  slot_start: string | null;
  slot_end: string | null;
  scheduled: boolean;
}

export interface PaymentLine {
  status: PaymentState;
  paid_total_paise: number;
  currency: string;
  last_paid_at: string | null;
  payment_count: number;
}

export interface Candidate {
  id: string;
  pentrix_user_id: string;
  full_name: string;
  email: string;
  phone: string | null;
  email_verified: boolean;
  registered_at: string;
  assessment: AssessmentLine;
  booking: BookingLine | null;
  payment: PaymentLine;
  enrolled: boolean;
  last_activity_at: string | null;
}

export interface CandidatePage {
  items: Candidate[];
  total: number;
  page: number;
  page_size: number;
}

/** Each group narrows the list; the groups combine (qualified AND not paid AND no booking). */
export interface CandidateFilters {
  q: string;
  assessment: string;
  qualification: string;
  booking: string;
  payment: string;
  registered_from: string;
  registered_to: string;
  sort: string;
  order: "asc" | "desc";
  page: number;
}

export const EMPTY_FILTERS: CandidateFilters = {
  q: "", assessment: "", qualification: "", booking: "", payment: "", registered_from: "", registered_to: "", sort: "registered", order: "desc", page: 1,
};

export interface Overview {
  configured: boolean;
  last_synced_at: string | null;
  last_sync_error: string | null;
  totals: {
    registered: number;
    registered_today: number;
    registered_last_7_days: number;
    assessments_completed: number;
    assessments_in_progress: number;
    qualified: number;
    not_qualified: number;
    paid: number;
    payment_pending: number;
  };
  bookings: { upcoming: number; today: number };
  funnel: { key: string; label: string; count: number }[];
  payment_status: Record<PaymentState, number>;
  recent_registrations: Candidate[];
}

/** Pentrix's own shape for one candidate's full record. */
export interface AttemptPart {
  total: number;
  answered: number;
  correct: number;
}

export interface Attempt {
  id: string;
  status: string;
  readiness_commitment_pct: number | null;
  technical_pct: number | null;
  qualified: boolean | null;
  started_at: string | null;
  submitted_at: string | null;
  duration_seconds: number | null;
  parts: Record<string, AttemptPart>;
}

export interface AssessmentRecord {
  state: AssessmentState;
  criteria: { readiness_commitment_pct: number; technical_pct: number };
  qualified: boolean | null;
  qualified_at: string | null;
  attempts: Attempt[];
}

export interface ProfilePayment {
  id: string;
  provider: string;
  amount_paise: number;
  currency: string;
  purpose: string;
  status: string;
  reference: string | null;
  invoice_number: string | null;
  receipt_number: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProfileBooking {
  id: string;
  reference: string | null;
  slot_start: string;
  slot_end: string;
  duration_minutes: number;
  status: string;
  assigned_staff_name: string | null;
  meeting_url: string | null;
  reschedule_count: number;
  cancelled_by: string | null;
}

export interface Profile {
  registration: {
    id: string;
    full_name: string;
    email: string;
    phone: string | null;
    email_verified: boolean;
    registered_at: string;
    sign_in: "google" | "password";
    terms_accepted_at: string | null;
    terms_version: string | null;
    privacy_version: string | null;
  };
  assessment: AssessmentRecord;
  bookings: ProfileBooking[];
  payments: ProfilePayment[];
  enrollment: { status: string; current_module: string | null; attendance_pct: number; task_completion_pct: number; enrolled_at: string } | null;
  activity: { action: string; at: string | null; by: string | null; changes: Record<string, { from: string | null; to: string | null }> | null }[];
}

export interface EmailLine {
  id: string;
  subject: string;
  status: string;
  template_key: string | null;
  module: string | null;
  error: string | null;
  sent_at: string;
}

export interface CandidateDetail {
  candidate: Candidate;
  live: boolean;
  error: string | null;
  profile: Profile | null;
  emails: EmailLine[];
}

export interface AssessmentDetail {
  candidate: Candidate;
  live: boolean;
  error: string | null;
  assessment: AssessmentRecord | null;
}

export const candidateKeys = {
  overview: ["pentrix-ops", "overview"] as const,
  list: (kind: "candidates" | "assessments", f: CandidateFilters) => ["pentrix-ops", kind, f] as const,
  detail: (id: string) => ["pentrix-ops", "candidate", id] as const,
  assessment: (id: string) => ["pentrix-ops", "assessment", id] as const,
};

export function candidateParams(f: CandidateFilters): URLSearchParams {
  const p = new URLSearchParams();
  const add = (key: string, value: string) => value && p.append(key, value);
  add("q", f.q);
  add("assessment", f.assessment);
  add("qualification", f.qualification);
  add("booking", f.booking);
  add("payment", f.payment);
  // dates are chosen as whole days in India: from the start of the first day to the end of the last
  if (f.registered_from) p.append("registered_from", new Date(`${f.registered_from}T00:00:00+05:30`).toISOString());
  if (f.registered_to) p.append("registered_to", new Date(new Date(`${f.registered_to}T00:00:00+05:30`).getTime() + 86_400_000).toISOString());
  p.append("sort", f.sort);
  p.append("order", f.order);
  p.append("page", String(f.page));
  p.append("page_size", "25");
  return p;
}

export const candidatesApi = {
  overview: () => apiClient.get<Overview>(`${base}/overview`).then((r) => r.data),
  list: (f: CandidateFilters) => apiClient.get<CandidatePage>(`${base}/candidates`, { params: candidateParams(f) }).then((r) => r.data),
  assessments: (f: CandidateFilters) => apiClient.get<CandidatePage>(`${base}/assessments`, { params: candidateParams(f) }).then((r) => r.data),
  detail: (id: string) => apiClient.get<CandidateDetail>(`${base}/candidates/${id}`).then((r) => r.data),
  assessment: (id: string) => apiClient.get<AssessmentDetail>(`${base}/assessments/${id}`).then((r) => r.data),
  edit: (id: string, changes: { full_name?: string; phone?: string | null }) => apiClient.patch<Candidate>(`${base}/candidates/${id}`, changes).then((r) => r.data),
  sync: () => apiClient.post<{ updated: number }>(`${base}/candidates/sync`).then((r) => r.data),
};

export const useOverview = (enabled = true) =>
  useQuery({ queryKey: candidateKeys.overview, queryFn: candidatesApi.overview, refetchInterval: 60_000, enabled, retry: false });
export const useCandidates = (f: CandidateFilters) =>
  useQuery({ queryKey: candidateKeys.list("candidates", f), queryFn: () => candidatesApi.list(f), refetchInterval: 60_000 });
export const useAssessments = (f: CandidateFilters) =>
  useQuery({ queryKey: candidateKeys.list("assessments", f), queryFn: () => candidatesApi.assessments(f), refetchInterval: 60_000 });
export const useCandidateDetail = (id: string) => useQuery({ queryKey: candidateKeys.detail(id), queryFn: () => candidatesApi.detail(id) });
export const useAssessmentDetail = (id: string) => useQuery({ queryKey: candidateKeys.assessment(id), queryFn: () => candidatesApi.assessment(id) });
