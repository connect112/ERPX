import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

// ------------------------------------------------------------------ the settings a letter is made from

export type Alignment = "left" | "center" | "right";

export interface CompanyInfo {
  name: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  signatory_name: string;
  signatory_designation: string;
}

export interface Branding {
  brand_color: string;
  font_family: "helvetica" | "times" | "courier";
  font_size: number;
  text_align: "left" | "justify";
  margin_top_mm: number;
  margin_bottom_mm: number;
  margin_left_mm: number;
  margin_right_mm: number;
  header_text: string;
  footer_text: string;
  show_page_numbers: boolean;
  show_extra_image: boolean;
  logo: { show: boolean; position: Alignment; width_mm: number; height_mm: number; spacing_mm: number };
  watermark: {
    show: boolean;
    size_percent: number;
    position: "center" | "top" | "bottom";
    offset_x_mm: number;
    offset_y_mm: number;
    opacity: number;
    pages: "all" | "first" | "last";
  };
  signature: { width_mm: number; height_mm: number; position: Alignment; show_stamp: boolean; stamp_size_mm: number };
}

export interface Phase {
  label: string;
  title: string;
}

export interface Programme {
  name: string;
  position: string;
  duration: string;
  start_date: string | null;
  end_date: string | null;
  program_type: "unpaid" | "paid";
  stipend: string;
  description: string;
  phases: Phase[];
}

export type SelectionReason = "hackathon" | "workshop" | "technical_evaluation" | "direct_selection" | "custom";

export interface FinancialNote {
  enabled: boolean;
  approved: boolean;
  amount: string;
  purpose: string;
  payment_conditions: string;
  refund_terms: string;
}

export interface Content {
  subject: string;
  selection_reason: SelectionReason;
  custom_reason: string;
  introduction: string;
  documents_intro: string;
  documents: string[];
  terms: string[];
  confirmation: string;
  closing: string;
  acceptance: string;
  guardian_required: boolean;
  guardian_acceptance: string;
  show_registration_id: boolean;
  notes: string[];
  financial_note: FinancialNote;
  start_documentation_on_new_page: boolean;
  letter_date: string | null;
}

export interface LetterConfig {
  company: CompanyInfo;
  branding: Branding;
  programme: Programme;
  content: Content;
  email: { subject: string; body: string };
}

export type AssetKind = "logo" | "watermark" | "signature" | "stamp" | "extra";

export interface LetterAsset {
  kind: AssetKind;
  label: string;
  source: "internship" | "defaults";
  filename: string;
  content_type: string;
  size_bytes: number;
  updated_at: string;
}

export type DesignState = "not_approved" | "approved" | "changed";

export interface LetterSettings {
  config: LetterConfig;
  defaults: LetterConfig;
  has_overrides: boolean;
  assets: Record<AssetKind, LetterAsset | null>;
  design_state: DesignState;
  design_approved_at: string | null;
  problems: string[];
  placeholders: Record<string, string>;
  internship_title: string;
  counts: Record<string, number>;
}

// ------------------------------------------------------------------ the letters

export type LetterStatus = "pending" | "generating" | "ready" | "failed" | "approved" | "released";
export type RowStatus = LetterStatus | "missing_data" | "not_generated";

export interface Letter {
  id: string;
  version: number;
  reference: string;
  status: LetterStatus;
  outdated: boolean;
  error: string | null;
  filename: string | null;
  page_count: number | null;
  pdf_size: number | null;
  generated_at: string | null;
  approved_at: string | null;
  delivery_status: "none" | "queued" | "sent" | "failed";
  delivery_attempts: number;
  delivery_error: string | null;
  released_at: string | null;
  sent_to_email: string | null;
}

export interface LetterStudent {
  student_id: string;
  name: string;
  email: string;
  institution: string;
  location: string;
  issues: string[];
  status: RowStatus;
  letter: Letter | null;
}

export interface LetterStudents {
  students: LetterStudent[];
  counts: Record<string, number>;
  in_progress: number;
}

export interface GenerateResult {
  queued: number;
  already_generated: number;
  in_progress: number;
  blocked: { student_id: string; name: string; issues: string[] }[];
  message: string;
}

export interface ReleaseResult {
  queued: number;
  skipped: { letter_id: string; name: string; reason: string }[];
  message: string;
}

export interface EmailPreview {
  to: string;
  subject: string;
  body: string;
  attachment: string;
}

export interface Delivery {
  id: string;
  letter_id: string;
  student_name: string;
  recipient_email: string;
  subject: string | null;
  status: "queued" | "sent" | "failed";
  attempt: number;
  error: string | null;
  created_at: string;
}

export interface LetterEvent {
  id: string;
  action: string;
  detail: string | null;
  letter_id: string | null;
  actor_user_id: string | null;
  created_at: string;
}

export const letterKeys = {
  all: (id: string) => ["our-internships", "letters", id] as const,
  settings: (id: string) => ["our-internships", "letters", id, "settings"] as const,
  students: (id: string) => ["our-internships", "letters", id, "students"] as const,
  deliveries: (id: string) => ["our-internships", "letters", id, "deliveries"] as const,
  events: (id: string) => ["our-internships", "letters", id, "events"] as const,
};

const base = (id: string) => `/our-internships/${id}/offer-letters`;
const multipart = { headers: { "Content-Type": "multipart/form-data" } };

export const lettersApi = {
  settings: (id: string) => apiClient.get<LetterSettings>(base(id)).then((r) => r.data),
  saveConfig: (id: string, config: LetterConfig, scope: "internship" | "defaults") =>
    apiClient.put<{ message: string }>(`${base(id)}/config`, { config, scope }).then((r) => r.data),
  resetConfig: (id: string) => apiClient.delete<{ message: string }>(`${base(id)}/config`).then((r) => r.data),
  uploadAsset: (id: string, kind: AssetKind, file: File, scope: "internship" | "defaults") => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.put<{ message: string }>(`${base(id)}/assets/${kind}`, form, { ...multipart, params: { scope } }).then((r) => r.data);
  },
  removeAsset: (id: string, kind: AssetKind, scope: "internship" | "defaults") =>
    apiClient.delete<{ message: string }>(`${base(id)}/assets/${kind}`, { params: { scope } }).then((r) => r.data),
  assetImage: (id: string, kind: AssetKind) =>
    apiClient.get<Blob>(`${base(id)}/assets/${kind}`, { responseType: "blob" }).then((r) => r.data),
  /** The PDF of a preview (a sample, or one student's letter) made from the given, possibly unsaved, settings. */
  preview: async (id: string, studentId: string | null, config: LetterConfig | null) => {
    const r = await apiClient.post<Blob>(`${base(id)}/preview`, { student_id: studentId, config }, { responseType: "blob" });
    return { blob: r.data, pages: Number(r.headers["x-letter-pages"] ?? 0), sample: r.headers["x-letter-sample"] === "1" };
  },
  approveDesign: (id: string) => apiClient.post<{ message: string }>(`${base(id)}/approve-design`).then((r) => r.data),
  students: (id: string) => apiClient.get<LetterStudents>(`${base(id)}/students`).then((r) => r.data),
  generate: (id: string, payload: { student_ids?: string[]; regenerate?: boolean }) =>
    apiClient.post<GenerateResult>(`${base(id)}/generate`, payload).then((r) => r.data),
  letterPdf: (id: string, letterId: string) =>
    apiClient.get<Blob>(`${base(id)}/letters/${letterId}/pdf`, { responseType: "blob" }).then((r) => r.data),
  versions: (id: string, studentId: string) => apiClient.get<Letter[]>(`${base(id)}/students/${studentId}/versions`).then((r) => r.data),
  approve: (id: string, letterIds: string[] | null) =>
    apiClient.post<{ message: string }>(`${base(id)}/approve`, { letter_ids: letterIds }).then((r) => r.data),
  zip: (id: string, letterIds: string[]) =>
    apiClient.get<Blob>(`${base(id)}/download.zip`, { responseType: "blob", params: { letter_id: letterIds }, paramsSerializer: { indexes: null } }).then((r) => r.data),
  emailPreview: (id: string, studentId: string | null) => apiClient.post<EmailPreview>(`${base(id)}/email-preview`, { student_id: studentId }).then((r) => r.data),
  testEmail: (id: string, toEmail: string) => apiClient.post<{ message: string }>(`${base(id)}/test-email`, { to_email: toEmail }).then((r) => r.data),
  release: (id: string, letterIds: string[], resend: boolean) =>
    apiClient.post<ReleaseResult>(`${base(id)}/release`, { letter_ids: letterIds, resend }).then((r) => r.data),
  deliveries: (id: string) => apiClient.get<Delivery[]>(`${base(id)}/deliveries`).then((r) => r.data),
  events: (id: string) => apiClient.get<LetterEvent[]>(`${base(id)}/events`).then((r) => r.data),
};

export function useLetterSettings(internshipId: string) {
  return useQuery({ queryKey: letterKeys.settings(internshipId), queryFn: () => lettersApi.settings(internshipId) });
}

/** The students and their letters. While a batch is being made it refreshes itself, so progress moves on screen. */
export function useLetterStudents(internshipId: string) {
  return useQuery({
    queryKey: letterKeys.students(internshipId),
    queryFn: () => lettersApi.students(internshipId),
    refetchInterval: (query) => ((query.state.data?.in_progress ?? 0) > 0 || (query.state.data?.students.some((s) => s.letter?.delivery_status === "queued") ?? false) ? 2500 : false),
  });
}
