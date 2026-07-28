import { apiClient } from "@/api/client";
import type { CourseLevel } from "@/features/courses/schemas/course-schemas";

export interface CoursePublic {
  id: string;
  organization_id: string;
  category_id: string | null;
  title: string;
  slug: string;
  short_description: string | null;
  description: string | null;
  thumbnail_url: string | null;
  level: CourseLevel;
  duration_hours: number | null;
  price: number;
  is_published: boolean;
  created_at: string;
}

export interface CourseListResponse {
  items: CoursePublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface CourseListParams {
  category_id?: string;
  is_published?: boolean;
  skip?: number;
  limit?: number;
}

export interface CourseCreatePayload {
  category_id?: string;
  title: string;
  slug: string;
  short_description?: string;
  description?: string;
  thumbnail_url?: string;
  level: CourseLevel;
  duration_hours?: number;
  price?: number;
}

export interface CourseUpdatePayload {
  category_id?: string;
  title?: string;
  short_description?: string;
  description?: string;
  thumbnail_url?: string;
  level?: CourseLevel;
  duration_hours?: number;
  price?: number;
  is_published?: boolean;
}

export const coursesApi = {
  list: (params: CourseListParams) =>
    apiClient.get<CourseListResponse>("/courses/", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<CoursePublic>(`/courses/${id}`).then((r) => r.data),

  create: (payload: CourseCreatePayload) =>
    apiClient.post<CoursePublic>("/courses/", payload).then((r) => r.data),

  update: (id: string, payload: CourseUpdatePayload) =>
    apiClient.patch<CoursePublic>(`/courses/${id}`, payload).then((r) => r.data),

  publish: (id: string) => apiClient.post<CoursePublic>(`/courses/${id}/publish`).then((r) => r.data),

  unpublish: (id: string) =>
    apiClient.post<CoursePublic>(`/courses/${id}/unpublish`).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/courses/${id}`).then((r) => r.data),
};
