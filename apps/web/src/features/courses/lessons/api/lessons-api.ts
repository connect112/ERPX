import { apiClient } from "@/api/client";
import type { LessonContentType } from "@/features/courses/lessons/schemas/lesson-schemas";

export interface LessonPublic {
  id: string;
  chapter_id: string;
  title: string;
  content_type: LessonContentType;
  video_url: string | null;
  content_text: string | null;
  duration_minutes: number | null;
  order_index: number;
  is_preview: boolean;
  created_at: string;
}

export interface LessonCreatePayload {
  title: string;
  content_type: LessonContentType;
  video_url?: string;
  content_text?: string;
  duration_minutes?: number;
  order_index: number;
  is_preview?: boolean;
}

export interface LessonUpdatePayload {
  title?: string;
  content_type?: LessonContentType;
  video_url?: string;
  content_text?: string;
  duration_minutes?: number;
  order_index?: number;
  is_preview?: boolean;
}

export const lessonsApi = {
  list: (courseId: string, chapterId: string) =>
    apiClient
      .get<LessonPublic[]>(`/courses/${courseId}/chapters/${chapterId}/lessons`)
      .then((r) => r.data),

  create: (courseId: string, chapterId: string, payload: LessonCreatePayload) =>
    apiClient
      .post<LessonPublic>(`/courses/${courseId}/chapters/${chapterId}/lessons`, payload)
      .then((r) => r.data),

  update: (courseId: string, chapterId: string, lessonId: string, payload: LessonUpdatePayload) =>
    apiClient
      .patch<LessonPublic>(
        `/courses/${courseId}/chapters/${chapterId}/lessons/${lessonId}`,
        payload
      )
      .then((r) => r.data),

  remove: (courseId: string, chapterId: string, lessonId: string) =>
    apiClient
      .delete(`/courses/${courseId}/chapters/${chapterId}/lessons/${lessonId}`)
      .then((r) => r.data),
};
