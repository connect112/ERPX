import { apiClient } from "@/api/client";

export interface VivaPublic {
  id: string;
  course_id: string;
  title: string;
  exam_date: string;
  panel_members: string | null;
  total_marks: number;
  passing_marks: number;
  created_at: string;
}

export interface VivaResultPublic {
  id: string;
  viva_id: string;
  student_id: string;
  score: number;
  remarks: string | null;
  evaluated_by_user_id: string | null;
  evaluated_at: string;
}

export interface VivaCreatePayload {
  title: string;
  exam_date: string;
  panel_members?: string;
  total_marks?: number;
  passing_marks?: number;
}

const base = (courseId: string) => `/examinations/courses/${courseId}/viva`;

export const vivaApi = {
  list: (courseId: string) => apiClient.get<VivaPublic[]>(base(courseId)).then((r) => r.data),

  create: (courseId: string, payload: VivaCreatePayload) =>
    apiClient.post<VivaPublic>(base(courseId), payload).then((r) => r.data),

  remove: (courseId: string, vivaId: string) =>
    apiClient.delete(`${base(courseId)}/${vivaId}`).then((r) => r.data),

  listResults: (courseId: string, vivaId: string) =>
    apiClient.get<VivaResultPublic[]>(`${base(courseId)}/${vivaId}/results`).then((r) => r.data),

  recordResult: (
    courseId: string,
    vivaId: string,
    payload: { student_id: string; score: number; remarks?: string }
  ) =>
    apiClient
      .post<VivaResultPublic>(`${base(courseId)}/${vivaId}/results`, payload)
      .then((r) => r.data),
};
