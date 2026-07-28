import { apiClient } from "@/api/client";
import type { SubmissionStatus } from "@/features/lms/assignments/schemas/assignment-schemas";

export interface AssignmentPublic {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  due_date: string | null;
  max_score: number;
  created_at: string;
}

export interface SubmissionPublic {
  id: string;
  assignment_id: string;
  student_id: string;
  content_url: string | null;
  content_text: string | null;
  submitted_at: string;
  status: SubmissionStatus;
  score: number | null;
  feedback: string | null;
  created_at: string;
}

export interface AssignmentCreatePayload {
  title: string;
  description?: string;
  due_date?: string;
  max_score?: number;
}

export interface AssignmentUpdatePayload {
  title?: string;
  description?: string;
  due_date?: string;
  max_score?: number;
}

export interface SubmissionCreatePayload {
  student_id: string;
  content_url?: string;
  content_text?: string;
}

export interface SubmissionGradePayload {
  score: number;
  feedback?: string;
}

const base = (courseId: string) => `/lms/courses/${courseId}/assignments`;

export const assignmentsApi = {
  list: (courseId: string) => apiClient.get<AssignmentPublic[]>(base(courseId)).then((r) => r.data),

  create: (courseId: string, payload: AssignmentCreatePayload) =>
    apiClient.post<AssignmentPublic>(base(courseId), payload).then((r) => r.data),

  update: (courseId: string, assignmentId: string, payload: AssignmentUpdatePayload) =>
    apiClient.patch<AssignmentPublic>(`${base(courseId)}/${assignmentId}`, payload).then((r) => r.data),

  remove: (courseId: string, assignmentId: string) =>
    apiClient.delete(`${base(courseId)}/${assignmentId}`).then((r) => r.data),

  listSubmissions: (courseId: string, assignmentId: string) =>
    apiClient
      .get<SubmissionPublic[]>(`${base(courseId)}/${assignmentId}/submissions`)
      .then((r) => r.data),

  submit: (courseId: string, assignmentId: string, payload: SubmissionCreatePayload) =>
    apiClient
      .post<SubmissionPublic>(`${base(courseId)}/${assignmentId}/submissions`, payload)
      .then((r) => r.data),

  grade: (courseId: string, assignmentId: string, submissionId: string, payload: SubmissionGradePayload) =>
    apiClient
      .post<SubmissionPublic>(
        `${base(courseId)}/${assignmentId}/submissions/${submissionId}/grade`,
        payload
      )
      .then((r) => r.data),
};
