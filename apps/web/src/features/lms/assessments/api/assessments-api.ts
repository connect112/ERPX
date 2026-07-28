import { apiClient } from "@/api/client";
import type {
  AssessmentType,
  AttemptStatus,
} from "@/features/lms/assessments/schemas/assessment-schemas";

export interface AssessmentPublic {
  id: string;
  course_id: string;
  title: string;
  assessment_type: AssessmentType;
  total_marks: number;
  passing_marks: number;
  duration_minutes: number | null;
  is_published: boolean;
  created_at: string;
}

export interface AttemptPublic {
  id: string;
  assessment_id: string;
  student_id: string;
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  status: AttemptStatus;
}

export interface AssessmentCreatePayload {
  title: string;
  assessment_type: AssessmentType;
  total_marks?: number;
  passing_marks?: number;
  duration_minutes?: number;
}

export interface AssessmentUpdatePayload {
  title?: string;
  total_marks?: number;
  passing_marks?: number;
  duration_minutes?: number;
  is_published?: boolean;
}

const base = (courseId: string) => `/lms/courses/${courseId}/assessments`;

export const assessmentsApi = {
  list: (courseId: string) => apiClient.get<AssessmentPublic[]>(base(courseId)).then((r) => r.data),

  create: (courseId: string, payload: AssessmentCreatePayload) =>
    apiClient.post<AssessmentPublic>(base(courseId), payload).then((r) => r.data),

  update: (courseId: string, assessmentId: string, payload: AssessmentUpdatePayload) =>
    apiClient.patch<AssessmentPublic>(`${base(courseId)}/${assessmentId}`, payload).then((r) => r.data),

  remove: (courseId: string, assessmentId: string) =>
    apiClient.delete(`${base(courseId)}/${assessmentId}`).then((r) => r.data),

  listAttempts: (courseId: string, assessmentId: string) =>
    apiClient
      .get<AttemptPublic[]>(`${base(courseId)}/${assessmentId}/attempts`)
      .then((r) => r.data),

  startAttempt: (courseId: string, assessmentId: string, studentId: string) =>
    apiClient
      .post<AttemptPublic>(`${base(courseId)}/${assessmentId}/attempts`, { student_id: studentId })
      .then((r) => r.data),

  submitAttempt: (courseId: string, assessmentId: string, attemptId: string, score: number) =>
    apiClient
      .post<AttemptPublic>(`${base(courseId)}/${assessmentId}/attempts/${attemptId}/submit`, { score })
      .then((r) => r.data),
};
