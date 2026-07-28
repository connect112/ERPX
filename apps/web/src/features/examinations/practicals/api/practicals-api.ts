import { apiClient } from "@/api/client";

export interface PracticalPublic {
  id: string;
  course_id: string;
  title: string;
  exam_date: string;
  rubric: string | null;
  total_marks: number;
  passing_marks: number;
  created_at: string;
}

export interface PracticalResultPublic {
  id: string;
  practical_id: string;
  student_id: string;
  score: number;
  remarks: string | null;
  evaluated_by_user_id: string | null;
  evaluated_at: string;
}

export interface PracticalCreatePayload {
  title: string;
  exam_date: string;
  rubric?: string;
  total_marks?: number;
  passing_marks?: number;
}

const base = (courseId: string) => `/examinations/courses/${courseId}/practicals`;

export const practicalsApi = {
  list: (courseId: string) => apiClient.get<PracticalPublic[]>(base(courseId)).then((r) => r.data),

  create: (courseId: string, payload: PracticalCreatePayload) =>
    apiClient.post<PracticalPublic>(base(courseId), payload).then((r) => r.data),

  remove: (courseId: string, practicalId: string) =>
    apiClient.delete(`${base(courseId)}/${practicalId}`).then((r) => r.data),

  listResults: (courseId: string, practicalId: string) =>
    apiClient
      .get<PracticalResultPublic[]>(`${base(courseId)}/${practicalId}/results`)
      .then((r) => r.data),

  recordResult: (
    courseId: string,
    practicalId: string,
    payload: { student_id: string; score: number; remarks?: string }
  ) =>
    apiClient
      .post<PracticalResultPublic>(`${base(courseId)}/${practicalId}/results`, payload)
      .then((r) => r.data),
};
