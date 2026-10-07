import axios from "axios";

import { apiClient } from "@/api/client";

export type ExamStatus = "draft" | "open" | "closed";

export type InfoFieldType = "text" | "phone" | "select";

export interface InfoField {
  key: string;
  label: string;
  required: boolean;
  type: InfoFieldType;
  options: string[];
}

export type CertificateFont =
  | "sans_bold"
  | "serif_bold"
  | "serif_bold_italic"
  | "great_vibes"
  | "allura"
  | "alex_brush"
  | "pinyon_script"
  | "parisienne";

/** Where and how each student's name is printed on the uploaded design (fractions of the page). */
export interface CertificateLayout {
  name_x: number;
  name_y: number;
  font_size: number;
  max_width: number;
  color: string;
  /** Second colour: the name is painted as a left-to-right gradient from `color` to this. */
  color_end: string | null;
  font: CertificateFont;
  show_verification: boolean;
  /** Print the certificate ID (left-aligned at id_x / id_y, e.g. after a "Certificate ID:" label). */
  show_id: boolean;
  id_x: number;
  id_y: number;
  id_font_size: number;
  id_color: string;
  id_font: CertificateFont;
}

export const DEFAULT_CERTIFICATE_LAYOUT: CertificateLayout = {
  name_x: 0.5,
  name_y: 0.5,
  font_size: 0.07,
  max_width: 0.7,
  color: "#1f2937",
  color_end: null,
  font: "sans_bold",
  show_verification: false,
  show_id: false,
  id_x: 0.82,
  id_y: 0.27,
  id_font_size: 0.018,
  id_color: "#1f2937",
  id_font: "sans_bold",
};

export interface WorkshopExam {
  id: string;
  workshop_id: string | null;
  title: string;
  description: string | null;
  duration_minutes: number;
  status: ExamStatus;
  show_result: boolean;
  public_code: string;
  info_fields: InfoField[];
  certificate_release_at: string | null;
  certificates_dispatched_at: string | null;
  certificate_heading: string;
  certificate_text: string | null;
  has_certificate_template: boolean;
  certificate_layout: CertificateLayout | null;
  /** How certificate IDs look, e.g. "GIR-{YYYY}-{#4}"; null = the default style. */
  certificate_id_pattern: string | null;
  certificate_id_start: number;
  question_count: number;
  attendee_count: number;
  created_at: string;
}

export interface ExamCreatePayload {
  title: string;
  description?: string | null;
  duration_minutes: number;
  info_fields?: InfoField[];
}

export interface ExamUpdatePayload {
  title?: string;
  description?: string | null;
  duration_minutes?: number;
  show_result?: boolean;
  certificate_heading?: string;
  certificate_text?: string | null;
  certificate_release_at?: string | null;
  info_fields?: InfoField[];
  certificate_layout?: CertificateLayout;
  /** "" clears it (back to the default style). */
  certificate_id_pattern?: string;
  certificate_id_start?: number;
}

/** An ID format that has not been saved yet, so previews can show it. */
export interface CertificateIdDraft {
  id_pattern?: string;
  id_start?: number;
}

export interface QuestionInput {
  text: string;
  options: string[];
  correct_indices: number[];
  allow_multiple: boolean;
  marks: number;
}

export interface Question extends QuestionInput {
  id: string;
  order_index: number;
}

export interface AttendeeInput {
  name: string;
  email: string;
}

export interface Attendee {
  id: string;
  name: string;
  email: string;
  info: Record<string, string>;
  invited_at: string | null;
  started_at: string | null;
  submitted_at: string | null;
  score: number | null;
  total_marks: number | null;
  certificate_number: string | null;
  certificate_sent_at: string | null;
  /** Only here to receive a certificate (e.g. a hackathon participant); not part of the exam. */
  certificate_only: boolean;
}

export interface Dashboard {
  total_attendees: number;
  /** People given a certificate only (they are not counted in the exam numbers). */
  certificate_only: number;
  invited: number;
  not_started: number;
  in_progress: number;
  submitted: number;
  certificates_sent: number;
  average_score_percent: number | null;
  attendees: Attendee[];
}

export type HackathonAudience = "all" | "teams" | "scored" | "top";

/** What will happen to each person: new / resend = a certificate is sent; the others are left alone. */
export type RecipientStatus = "new" | "resend" | "already_sent" | "on_exam" | "no_email";

export interface CertificateRecipient {
  name: string;
  email: string | null;
  team_name: string | null;
  status: RecipientStatus;
}

export interface HackathonCertificatesResult {
  hackathon_title: string;
  recipients: CertificateRecipient[];
  will_send: number;
  already_sent: number;
  on_exam: number;
  no_email: number;
  sent: boolean;
  message: string;
}

export const workshopExamsApi = {
  list: () => apiClient.get<WorkshopExam[]>("/workshop-exams").then((r) => r.data),
  get: (id: string) => apiClient.get<WorkshopExam>(`/workshop-exams/${id}`).then((r) => r.data),
  create: (payload: ExamCreatePayload) =>
    apiClient.post<WorkshopExam>("/workshop-exams", payload).then((r) => r.data),
  update: (id: string, payload: ExamUpdatePayload) =>
    apiClient.patch<WorkshopExam>(`/workshop-exams/${id}`, payload).then((r) => r.data),
  remove: (id: string) => apiClient.delete(`/workshop-exams/${id}`).then((r) => r.data),
  setStatus: (id: string, status: ExamStatus) =>
    apiClient.post<WorkshopExam>(`/workshop-exams/${id}/status`, { status }).then((r) => r.data),

  uploadCertificateTemplate: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    // apiClient defaults to a JSON Content-Type, under which axios turns a
    // FormData body into JSON; naming multipart lets the browser add the boundary.
    return apiClient
      .put<WorkshopExam>(`/workshop-exams/${id}/certificate/template`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  removeCertificateTemplate: (id: string) =>
    apiClient.delete<WorkshopExam>(`/workshop-exams/${id}/certificate/template`).then((r) => r.data),
  certificateTemplateImage: (id: string) =>
    apiClient
      .get<Blob>(`/workshop-exams/${id}/certificate/template`, { responseType: "blob" })
      .then((r) => r.data),
  certificatePreviewPdf: (id: string, layout: CertificateLayout, draft: CertificateIdDraft = {}) =>
    apiClient
      .post<Blob>(`/workshop-exams/${id}/certificate/preview`, { layout, ...draft }, { responseType: "blob" })
      .then((r) => r.data),
  emailTestCertificate: (id: string, email: string, layout: CertificateLayout, draft: CertificateIdDraft = {}) =>
    apiClient
      .post<{ message: string }>(`/workshop-exams/${id}/certificate/test-email`, { email, layout, ...draft })
      .then((r) => r.data),
  /** What IDs in this format look like (nothing is saved). Rejects with a message if the format is unusable. */
  certificateIdExamples: (id: string, pattern: string, start: number) =>
    apiClient
      .post<{ examples: string[] }>(`/workshop-exams/${id}/certificate/id-preview`, { pattern, start })
      .then((r) => r.data.examples),

  questions: (id: string) => apiClient.get<Question[]>(`/workshop-exams/${id}/questions`).then((r) => r.data),
  updateQuestion: (id: string, questionId: string, payload: QuestionInput) =>
    apiClient.put<Question>(`/workshop-exams/${id}/questions/${questionId}`, payload).then((r) => r.data),
  addQuestions: (id: string, questions: QuestionInput[]) =>
    apiClient.post<Question[]>(`/workshop-exams/${id}/questions`, { questions }).then((r) => r.data),
  deleteQuestion: (id: string, questionId: string) =>
    apiClient.delete(`/workshop-exams/${id}/questions/${questionId}`).then((r) => r.data),

  attendees: (id: string) => apiClient.get<Attendee[]>(`/workshop-exams/${id}/attendees`).then((r) => r.data),
  importAttendees: (id: string, attendees: AttendeeInput[]) =>
    apiClient
      .post<{ added: number; skipped_duplicates: number }>(`/workshop-exams/${id}/attendees`, { attendees })
      .then((r) => r.data),
  /** Correct a name and/or email; the personal exam link stays the same. */
  updateAttendee: (
    id: string,
    attendeeId: string,
    payload: { name?: string; email?: string; send_link?: boolean }
  ) => apiClient.patch<Attendee>(`/workshop-exams/${id}/attendees/${attendeeId}`, payload).then((r) => r.data),
  /** Delete one person's submission so they can sit the exam again with their link. */
  resetSubmission: (id: string, attendeeId: string) =>
    apiClient
      .post<{ message: string }>(`/workshop-exams/${id}/attendees/${attendeeId}/reset-submission`)
      .then((r) => r.data),
  /** Remove a person, their submission and any certificate issued to them. */
  deleteAttendee: (id: string, attendeeId: string) =>
    apiClient.delete<{ message: string }>(`/workshop-exams/${id}/attendees/${attendeeId}`).then((r) => r.data),
  sendInvites: (id: string, resendAll: boolean) =>
    apiClient
      .post<{ queued: number }>(`/workshop-exams/${id}/invites`, { resend_all: resendAll })
      .then((r) => r.data),

  dashboard: (id: string) => apiClient.get<Dashboard>(`/workshop-exams/${id}/dashboard`).then((r) => r.data),
  sendCertificatesNow: (id: string, includeInProgress = false) =>
    apiClient
      .post<{ message: string }>(`/workshop-exams/${id}/certificates/send-now`, {
        include_in_progress: includeInProgress,
      })
      .then((r) => r.data),
  /** Without confirm: who would get this exam's certificate from a hackathon. With confirm: add them and send. */
  hackathonCertificates: (
    id: string,
    payload: { hackathon_id: string; audience: HackathonAudience; top_n?: number; confirm: boolean }
  ) =>
    apiClient
      .post<HackathonCertificatesResult>(`/workshop-exams/${id}/certificates/hackathon`, payload)
      .then((r) => r.data),
  downloadResults: async (id: string) => {
    const response = await apiClient.get(`/workshop-exams/${id}/results.csv`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `exam-results-${id}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  },
};

// ---- Public attendee flow: deliberately NOT the shared apiClient ----
//
// That client attaches the signed-in user's token and, on a 401, logs them
// out and redirects. Attendees have no session, and an admin who opens a
// test link in the same browser must not get logged out by it.
const publicClient = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1" });

export type PublicState = "not_open" | "ready" | "in_progress" | "submitted" | "closed";

export interface PublicExamInfo {
  title: string;
  description: string | null;
  attendee_name: string;
  duration_minutes: number;
  question_count: number;
  state: PublicState;
  remaining_seconds: number | null;
  score: number | null;
  total_marks: number | null;
}

export interface PublicQuestion {
  id: string;
  text: string;
  marks: number;
  allow_multiple: boolean;
  options: { index: number; text: string }[];
}

export interface PublicStart {
  remaining_seconds: number;
  questions: PublicQuestion[];
  saved_answers: Record<string, number[]>;
}

export interface PublicJoinInfo {
  title: string;
  description: string | null;
  duration_minutes: number;
  question_count: number;
  info_fields: InfoField[];
  state: "open" | "not_open" | "closed";
}

export interface RegisterPayload {
  name: string;
  email: string;
  info: Record<string, string>;
}

export const publicExamApi = {
  info: (token: string) =>
    publicClient.get<PublicExamInfo>(`/public/workshop-exams/${token}`).then((r) => r.data),
  start: (token: string) =>
    publicClient.post<PublicStart>(`/public/workshop-exams/${token}/start`).then((r) => r.data),
  joinInfo: (code: string) =>
    publicClient.get<PublicJoinInfo>(`/public/workshop-exams/join/${code}`).then((r) => r.data),
  register: (code: string, payload: RegisterPayload) =>
    publicClient
      .post<{ token: string | null; already_registered: boolean }>(
        `/public/workshop-exams/join/${code}/register`,
        payload
      )
      .then((r) => r.data),
  saveAnswers: (token: string, answers: Record<string, number[]>) =>
    publicClient.put(`/public/workshop-exams/${token}/answers`, { answers }).then((r) => r.data),
  submit: (token: string, answers: Record<string, number[]>) =>
    publicClient
      .post<{ submitted: boolean; score: number | null; total_marks: number | null }>(
        `/public/workshop-exams/${token}/submit`,
        { answers }
      )
      .then((r) => r.data),
  verifyCertificate: (number: string) =>
    publicClient
      .get<{ valid: boolean; attendee_name?: string; exam_title?: string; issued_at?: string }>(
        `/public/workshop-certificates/verify/${encodeURIComponent(number)}`
      )
      .then((r) => r.data),
};
