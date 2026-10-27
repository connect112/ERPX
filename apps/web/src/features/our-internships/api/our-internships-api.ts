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
export type OfferFieldKey = "name" | "institution" | "internship" | "date" | "reference";
export type OfferFont = "sans" | "sans_bold" | "serif" | "serif_bold";

/** Where one detail is printed on the letter: fractions of the page, so it works at any size. */
export interface OfferField {
  key: OfferFieldKey;
  page: number;
  x: number;
  y: number;
  font_size: number;
  max_width: number;
  color: string;
  font: OfferFont;
  align: "left" | "center" | "right";
}

export interface OfferSettings {
  has_template: boolean;
  template_filename: string | null;
  template_pages: number | null;
  template_size: number | null;
  layout: { fields: OfferField[] } | null;
  email_subject: string;
  email_body: string;
  email_is_default: boolean;
  offer_date: string | null;
  placeholders: Record<string, string>;
  field_labels: Record<OfferFieldKey, string>;
  released_at: string | null;
  missing: string[];
  counts: { not_sent: number; queued: number; sent: number; failed: number; selected: number };
}

export const offerKeys = {
  settings: (id: string) => ["our-internships", "offer", id] as const,
  template: (id: string, size: number | null) => ["our-internships", "offer-template", id, size] as const,
};

const multipartHeaders = { headers: { "Content-Type": "multipart/form-data" } };

function openPdf(blob: Blob) {
  const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
  window.open(url, "_blank", "noopener");
  // the new tab has loaded it long before this
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const offersApi = {
  settings: (id: string) => apiClient.get<OfferSettings>(`/our-internships/${id}/offer`).then((r) => r.data),
  uploadTemplate: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.put<OfferSettings>(`/our-internships/${id}/offer/template`, form, multipartHeaders).then((r) => r.data);
  },
  removeTemplate: (id: string) => apiClient.delete<OfferSettings>(`/our-internships/${id}/offer/template`).then((r) => r.data),
  /** The uploaded PDF's bytes, for drawing the page while placing fields. */
  templateBytes: (id: string) =>
    apiClient.get<ArrayBuffer>(`/our-internships/${id}/offer/template`, { responseType: "arraybuffer" }).then((r) => r.data),
  saveLayout: (id: string, fields: OfferField[]) =>
    apiClient.put<OfferSettings>(`/our-internships/${id}/offer/layout`, { fields }).then((r) => r.data),
  saveEmail: (id: string, payload: { subject: string | null; body: string | null; offer_date: string | null }) =>
    apiClient.put<OfferSettings>(`/our-internships/${id}/offer/email`, payload).then((r) => r.data),
  /** A sample letter with the given (possibly unsaved) positions, opened in a new tab. */
  previewSample: async (id: string, fields?: OfferField[]) => {
    const r = await apiClient.post<Blob>(`/our-internships/${id}/offer/preview`, { layout: fields ? { fields } : null }, { responseType: "blob" });
    openPdf(r.data);
  },
  previewStudent: async (id: string, studentId: string) => {
    const r = await apiClient.get<Blob>(`/our-internships/${id}/selected/${studentId}/offer.pdf`, { responseType: "blob" });
    openPdf(r.data);
  },
  sendTest: (id: string, toEmail: string) =>
    apiClient.post<{ message: string }>(`/our-internships/${id}/offer/test-email`, { to_email: toEmail }).then((r) => r.data),
  release: (id: string, payload: { student_ids?: string[]; resend?: boolean } = {}) =>
    apiClient
      .post<{ queued: number; already_sent: number; message: string }>(`/our-internships/${id}/offers/release`, payload)
      .then((r) => r.data),
};
