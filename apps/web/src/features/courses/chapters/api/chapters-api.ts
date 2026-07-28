import { apiClient } from "@/api/client";

export interface ChapterPublic {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  order_index: number;
  created_at: string;
}

export interface ChapterCreatePayload {
  title: string;
  description?: string;
  order_index: number;
}

export interface ChapterUpdatePayload {
  title?: string;
  description?: string;
  order_index?: number;
}

export const chaptersApi = {
  list: (courseId: string) =>
    apiClient.get<ChapterPublic[]>(`/courses/${courseId}/chapters`).then((r) => r.data),

  create: (courseId: string, payload: ChapterCreatePayload) =>
    apiClient.post<ChapterPublic>(`/courses/${courseId}/chapters`, payload).then((r) => r.data),

  update: (courseId: string, chapterId: string, payload: ChapterUpdatePayload) =>
    apiClient
      .patch<ChapterPublic>(`/courses/${courseId}/chapters/${chapterId}`, payload)
      .then((r) => r.data),

  remove: (courseId: string, chapterId: string) =>
    apiClient.delete(`/courses/${courseId}/chapters/${chapterId}`).then((r) => r.data),
};
