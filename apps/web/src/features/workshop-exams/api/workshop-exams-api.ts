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
}

export interface Dashboard {
  total_attendees: number;
  invited: number;
  not_started: number;
  in_progress: number;
  submitted: number;
  certificates_sent: number;
  average_score_percent: number | null;
  attendees: Attendee[];
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
  sendInvites: (id: string, resendAll: boolean) =>
    apiClient
      .post<{ queued: number }>(`/workshop-exams/${id}/invites`, { resend_all: resendAll })
      .then((r) => r.data),

  dashboard: (id: string) => apiClient.get<Dashboard>(`/workshop-exams/${id}/dashboard`).then((r) => r.data),
  sendCertificatesNow: (id: string) =>
    apiClient.post<{ message: string }>(`/workshop-exams/${id}/certificates/send-now`).then((r) => r.data),
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
