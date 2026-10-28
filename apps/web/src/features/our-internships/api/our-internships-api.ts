import { apiClient } from "@/api/client";

export type InternshipScope = "institution" | "all";
export type InternshipStatus = "selecting" | "offers_released" | "closed";

export interface OurInternship {
  id: string;
  title: string;
  description: string | null;
  scope: InternshipScope;
  institution_id: string | null;
  institution_name: string | null;
  event_id: string | null;
  event_name: string | null;
  status: InternshipStatus;
  selected_count: number;
  offers_released_at: string | null;
  lms_course_id: string | null;
  lms_course_title: string | null;
  created_at: string;
}

export interface InternshipCreatePayload {
  title: string;
  description?: string | null;
  scope: InternshipScope;
  institution_id?: string | null;
  event_id?: string | null;
}

export interface ExamMark {
  exam_id: string;
  title: string;
  attended: boolean;
  score: number | null;
  total_marks: number | null;
}

export interface TeamRef {
  team_id: string;
  team_name: string;
  hackathon_id: string;
  hackathon_title: string;
  score: number;
  max_total: number;
  rank: number | null;
  tasks_scored: number;
}

export interface StudentPerformance {
  student_id: string;
  name: string;
  email: string;
  phone: string | null;
  details: Record<string, string>;
  institution_id: string;
  institution_name: string;
  event_id: string;
  event_name: string;
  individual_score: number | null;
  remarks: string | null;
  exams: ExamMark[];
  exam_score: number | null;
  exam_total: number | null;
  exam_percent: number | null;
  team: TeamRef | null;
  selected: boolean;
}

export interface TeamMember {
  name: string;
  email: string | null;
  student_id: string | null;
  exam_score: number | null;
  exam_total: number | null;
  individual_score: number | null;
  selected: boolean;
}

export interface TeamPerformance {
  team_id: string | null;
  team_name: string;
  hackathon_id: string | null;
  hackathon_title: string | null;
  event_id: string;
  event_name: string;
  institution_name: string;
  score: number | null;
  max_total: number | null;
  rank: number | null;
  tasks_scored: number;
  members: TeamMember[];
}

export interface PerformanceResponse {
  exams: { id: string; title: string; event_id: string; total_marks: number }[];
  hackathons: { id: string; title: string; event_id: string; max_total: number }[];
  students: StudentPerformance[];
  teams: TeamPerformance[];
  total_students: number;
}

export interface SelectedStudent {
  student_id: string;
  name: string;
  email: string;
  phone: string | null;
  institution_id: string;
  institution_name: string;
  note: string | null;
  selected_at: string;
  offer_reference: string | null;
  offer_status: OfferStatus;
  offer_sent_at: string | null;
  offer_error: string | null;
  offer_response: OfferResponse;
  offer_response_at: string | null;
  verification_status: VerificationStatus;
  verification_note: string | null;
  verified_at: string | null;
  payment_status: PaymentStatus;
  payment_amount: number | null;
  payment_reference: string | null;
  payment_received_on: string | null;
  payment_confirmed_at: string | null;
  lms_status: LmsStatus;
  lms_granted_at: string | null;
  /** Where the student is overall, and what (if anything) stops LMS access being granted right now. */
  stage: string;
  stage_label: string;
  grant_blockers: string[];
  standings: StudentPerformance[];
}

export const ourInternshipsKeys = {
  all: ["our-internships"] as const,
  list: () => ["our-internships", "list"] as const,
  detail: (id: string) => ["our-internships", "detail", id] as const,
  performance: (id: string, institutionId: string, eventId: string, q: string) =>
    ["our-internships", "performance", id, institutionId, eventId, q] as const,
  selected: (id: string) => ["our-internships", "selected", id] as const,
};

export const ourInternshipsApi = {
  list: () => apiClient.get<OurInternship[]>("/our-internships").then((r) => r.data),
  get: (id: string) => apiClient.get<OurInternship>(`/our-internships/${id}`).then((r) => r.data),
  create: (payload: InternshipCreatePayload) => apiClient.post<OurInternship>("/our-internships", payload).then((r) => r.data),
  update: (id: string, payload: { title?: string; description?: string | null; status?: InternshipStatus }) =>
    apiClient.patch<OurInternship>(`/our-internships/${id}`, payload).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/our-internships/${id}`).then((r) => r.data),

  performance: (id: string, filters: { institutionId?: string; eventId?: string; q?: string }) =>
    apiClient
      .get<PerformanceResponse>(`/our-internships/${id}/performance`, {
        params: { institution_id: filters.institutionId || undefined, event_id: filters.eventId || undefined, q: filters.q || undefined },
      })
      .then((r) => r.data),

  selected: (id: string) =>
    apiClient.get<{ items: SelectedStudent[]; total: number }>(`/our-internships/${id}/selected`).then((r) => r.data),
  select: (id: string, studentIds: string[], note?: string) =>
    apiClient.post<{ message: string }>(`/our-internships/${id}/selected`, { student_ids: studentIds, note: note || undefined }).then((r) => r.data),
  unselect: (id: string, studentId: string) => apiClient.delete(`/our-internships/${id}/selected/${studentId}`).then((r) => r.data),
  setNote: (id: string, studentId: string, note: string | null) =>
    apiClient.patch(`/our-internships/${id}/selected/${studentId}`, { note }).then((r) => r.data),
};

// ------------------------------------------------------------------ offer letters

export type OfferStatus = "not_sent" | "queued" | "sent" | "failed";
// Making, approving and emailing the letters is in letters-api.ts.

// ------------------------------------------------------- onboarding: verification, payment, LMS access

export type OfferResponse = "awaiting" | "accepted" | "declined";
export type VerificationStatus = "pending" | "verified" | "rejected";
export type PaymentStatus = "pending" | "paid";
export type LmsStatus = "not_granted" | "granted" | "revoked";

export interface OnboardingUpdate {
  offer_response?: OfferResponse;
  verification_status?: VerificationStatus;
  verification_note?: string | null;
  payment_status?: PaymentStatus;
  payment_amount?: number | null;
  payment_reference?: string | null;
  payment_received_on?: string | null;
}

export interface CourseOption {
  id: string;
  title: string;
  is_published: boolean;
}

export interface GrantResult {
  student_id: string;
  name: string;
  ok: boolean;
  message: string;
}

export const onboardingApi = {
  courses: (id: string) => apiClient.get<CourseOption[]>(`/our-internships/${id}/lms/courses`).then((r) => r.data),
  setCourse: (id: string, courseId: string | null) =>
    apiClient.patch<OurInternship>(`/our-internships/${id}`, { lms_course_id: courseId }).then((r) => r.data),
  student: (id: string, studentId: string) => apiClient.get<SelectedStudent>(`/our-internships/${id}/selected/${studentId}`).then((r) => r.data),
  update: (id: string, studentId: string, payload: OnboardingUpdate) =>
    apiClient.patch<SelectedStudent>(`/our-internships/${id}/selected/${studentId}/onboarding`, payload).then((r) => r.data),
  updateMany: (id: string, studentIds: string[], payload: { offer_response?: OfferResponse; verification_status?: VerificationStatus; payment_status?: PaymentStatus }) =>
    apiClient.post<{ changed: number; problems: string[] }>(`/our-internships/${id}/onboarding/bulk`, { student_ids: studentIds, ...payload }).then((r) => r.data),
  grant: (id: string, studentId: string) =>
    apiClient.post<SelectedStudent>(`/our-internships/${id}/selected/${studentId}/lms/grant`).then((r) => r.data),
  grantMany: (id: string, studentIds: string[]) =>
    apiClient.post<{ granted: number; results: GrantResult[] }>(`/our-internships/${id}/lms/grant`, { student_ids: studentIds }).then((r) => r.data),
  revoke: (id: string, studentId: string) =>
    apiClient.post<SelectedStudent>(`/our-internships/${id}/selected/${studentId}/lms/revoke`).then((r) => r.data),
};
