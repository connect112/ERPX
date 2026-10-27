import { apiClient } from "@/api/client";

export type AssignmentStatus = "draft" | "published" | "closed";

export interface StoredFile {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  url: string | null;
  created_at: string | null;
}

export interface AssignmentTask {
  id: string;
  title: string;
  details: string | null;
}

export interface RubricRule {
  id: string;
  criterion: string;
  points: number;
}

export interface Assignment {
  id: string;
  internship_id: string;
  title: string;
  description: string | null;
  tasks: AssignmentTask[];
  instructions: string | null;
  max_marks: number;
  rubric: RubricRule[];
  starts_at: string | null;
  deadline_at: string | null;
  allow_late: boolean;
  max_files: number;
  status: AssignmentStatus;
  created_at: string;
  files: StoredFile[];
  submitted_count: number;
  graded_count: number;
  enrolled_count: number;
}

export interface AssignmentPayload {
  title: string;
  description: string | null;
  tasks: AssignmentTask[];
  instructions: string | null;
  max_marks: number;
  rubric: RubricRule[];
  starts_at: string | null;
  deadline_at: string | null;
  allow_late: boolean;
  max_files: number;
  status?: AssignmentStatus;
}

export interface SubmissionRow {
  selection_id: string;
  student_name: string;
  student_email: string;
  submitted: boolean;
  submitted_at: string | null;
  is_late: boolean;
  resubmission_count: number;
  note: string | null;
  files: StoredFile[];
  rubric_scores: Record<string, number> | null;
  score: number | null;
  feedback: string | null;
  reviewed_at: string | null;
}

export interface GradePayload {
  rubric_scores?: Record<string, number> | null;
  score?: number | null;
  feedback?: string | null;
}

export interface ExamSummary {
  id: string;
  title: string;
  status: "draft" | "open" | "closed";
  duration_minutes: number;
  question_count: number;
  attendee_count: number;
  submitted_count: number;
  average_percent: number | null;
}

export interface AvailableExam {
  id: string;
  title: string;
  status: string;
}

export interface ExamResultRow {
  selection_id: string;
  student_name: string;
  student_email: string;
  state: "not_assigned" | "not_started" | "in_progress" | "submitted";
  score: number | null;
  total_marks: number | null;
  percent: number | null;
  submitted_at: string | null;
}

export interface ExamAssignResult {
  added: number;
  already_on_exam: number;
  invited: number;
}

export const learningKeys = {
  assignments: (id: string) => ["our-internships", "assignments", id] as const,
  submissions: (id: string, assignmentId: string) => ["our-internships", "assignments", id, assignmentId, "submissions"] as const,
  exams: (id: string) => ["our-internships", "exams", id] as const,
  availableExams: (id: string) => ["our-internships", "exams", id, "available"] as const,
  results: (id: string, examId: string) => ["our-internships", "exams", id, examId, "results"] as const,
};

const multipartHeaders = { headers: { "Content-Type": "multipart/form-data" } };
const base = (id: string) => `/our-internships/${id}`;

export const examsApi = {
  list: (id: string) => apiClient.get<ExamSummary[]>(`${base(id)}/exams`).then((r) => r.data),
  available: (id: string) => apiClient.get<AvailableExam[]>(`${base(id)}/exams/available`).then((r) => r.data),
  /** Create a new exam already belonging to this internship (the questions are added in the exam builder). */
  create: (id: string, title: string, durationMinutes: number) =>
    apiClient
      .post<{ id: string }>(`/workshop-exams`, { title, duration_minutes: durationMinutes, internship_id: id })
      .then((r) => r.data),
  link: (id: string, examId: string) => apiClient.post(`${base(id)}/exams/${examId}/link`).then((r) => r.data),
  unlink: (id: string, examId: string) => apiClient.delete(`${base(id)}/exams/${examId}/link`).then((r) => r.data),
  assign: (id: string, examId: string, sendInvites: boolean) =>
    apiClient.post<ExamAssignResult>(`${base(id)}/exams/${examId}/assign`, { send_invites: sendInvites }).then((r) => r.data),
  results: (id: string, examId: string) => apiClient.get<ExamResultRow[]>(`${base(id)}/exams/${examId}/results`).then((r) => r.data),
};

export const assignmentsApi = {
  list: (id: string) => apiClient.get<Assignment[]>(`${base(id)}/assignments`).then((r) => r.data),
  create: (id: string, payload: AssignmentPayload) => apiClient.post<Assignment>(`${base(id)}/assignments`, payload).then((r) => r.data),
  update: (id: string, assignmentId: string, payload: Partial<AssignmentPayload>) =>
    apiClient.patch<Assignment>(`${base(id)}/assignments/${assignmentId}`, payload).then((r) => r.data),
  remove: (id: string, assignmentId: string) => apiClient.delete(`${base(id)}/assignments/${assignmentId}`).then((r) => r.data),
  addFile: (id: string, assignmentId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<StoredFile>(`${base(id)}/assignments/${assignmentId}/files`, form, multipartHeaders).then((r) => r.data);
  },
  removeFile: (id: string, assignmentId: string, fileId: string) =>
    apiClient.delete(`${base(id)}/assignments/${assignmentId}/files/${fileId}`).then((r) => r.data),
  submissions: (id: string, assignmentId: string) =>
    apiClient.get<SubmissionRow[]>(`${base(id)}/assignments/${assignmentId}/submissions`).then((r) => r.data),
  grade: (id: string, assignmentId: string, selectionId: string, payload: GradePayload) =>
    apiClient
      .put<SubmissionRow>(`${base(id)}/assignments/${assignmentId}/submissions/${selectionId}/grade`, payload)
      .then((r) => r.data),
};
