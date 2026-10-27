import { apiClient } from "@/api/client";
import type { SubmissionMethod } from "@/features/our-internships/api/projects-api";

export interface Review {
  id: string;
  label: string;
  reviewer_name: string | null;
  factor_scores: Record<string, number> | null;
  total: number;
  max_total: number;
  feedback: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewRow {
  selection_id: string;
  student_name: string;
  student_email: string;
  method: SubmissionMethod;
  submitted_at: string;
  is_late: boolean;
  reviews: Review[];
  average: number | null;
  max_marks: number;
  final_marks: number | null;
  final_feedback: string | null;
  final_published_at: string | null;
}

export interface ReviewPayload {
  label: string;
  factor_scores?: Record<string, number> | null;
  score?: number | null;
  feedback?: string | null;
}

export interface Grant {
  selection_id: string;
  student_name: string;
  student_email: string;
  note: string | null;
  granted_at: string;
}

export interface Award {
  id: string;
  name: string;
  description: string | null;
  grants: Grant[];
}

export const reviewKeys = {
  rows: (id: string, projectId: string) => ["our-internships", "projects", id, projectId, "reviews"] as const,
  awards: (id: string) => ["our-internships", "awards", id] as const,
};

const base = (id: string) => `/our-internships/${id}`;

export const reviewsApi = {
  rows: (id: string, projectId: string) => apiClient.get<ReviewRow[]>(`${base(id)}/projects/${projectId}/reviews`).then((r) => r.data),
  add: (id: string, projectId: string, selectionId: string, payload: ReviewPayload) =>
    apiClient.post<ReviewRow>(`${base(id)}/projects/${projectId}/submissions/${selectionId}/reviews`, payload).then((r) => r.data),
  update: (id: string, projectId: string, reviewId: string, payload: ReviewPayload) =>
    apiClient.put<ReviewRow>(`${base(id)}/projects/${projectId}/reviews/${reviewId}`, payload).then((r) => r.data),
  remove: (id: string, projectId: string, reviewId: string) =>
    apiClient.delete<ReviewRow>(`${base(id)}/projects/${projectId}/reviews/${reviewId}`).then((r) => r.data),
  publish: (id: string, projectId: string, selectionId: string, payload: { final_marks: number | null; feedback: string | null }) =>
    apiClient.put<ReviewRow>(`${base(id)}/projects/${projectId}/submissions/${selectionId}/final`, payload).then((r) => r.data),
  unpublish: (id: string, projectId: string, selectionId: string) =>
    apiClient.delete<ReviewRow>(`${base(id)}/projects/${projectId}/submissions/${selectionId}/final`).then((r) => r.data),
};

export const awardsApi = {
  list: (id: string) => apiClient.get<Award[]>(`${base(id)}/awards`).then((r) => r.data),
  create: (id: string, payload: { name: string; description: string | null }) => apiClient.post<Award>(`${base(id)}/awards`, payload).then((r) => r.data),
  update: (id: string, awardId: string, payload: { name?: string; description?: string | null }) =>
    apiClient.patch<Award>(`${base(id)}/awards/${awardId}`, payload).then((r) => r.data),
  remove: (id: string, awardId: string) => apiClient.delete(`${base(id)}/awards/${awardId}`).then((r) => r.data),
  grant: (id: string, awardId: string, selectionId: string, note: string | null) =>
    apiClient.put<Award>(`${base(id)}/awards/${awardId}/grants`, { selection_id: selectionId, note }).then((r) => r.data),
  revoke: (id: string, awardId: string, selectionId: string) =>
    apiClient.delete<Award>(`${base(id)}/awards/${awardId}/grants/${selectionId}`).then((r) => r.data),
};
