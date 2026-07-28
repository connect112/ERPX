import { apiClient } from "@/api/client";
import type { ResourceType } from "@/features/courses/resources/schemas/resource-schemas";

export interface ResourcePublic {
  id: string;
  lesson_id: string;
  title: string;
  resource_type: ResourceType;
  file_url: string;
  is_downloadable: boolean;
  created_at: string;
}

export interface ResourceCreatePayload {
  title: string;
  resource_type: ResourceType;
  file_url: string;
  is_downloadable?: boolean;
}

export interface ResourceUpdatePayload {
  title?: string;
  resource_type?: ResourceType;
  file_url?: string;
  is_downloadable?: boolean;
}

const base = (courseId: string, chapterId: string, lessonId: string) =>
  `/courses/${courseId}/chapters/${chapterId}/lessons/${lessonId}/resources`;

export const resourcesApi = {
  list: (courseId: string, chapterId: string, lessonId: string) =>
    apiClient.get<ResourcePublic[]>(base(courseId, chapterId, lessonId)).then((r) => r.data),

  create: (courseId: string, chapterId: string, lessonId: string, payload: ResourceCreatePayload) =>
    apiClient
      .post<ResourcePublic>(base(courseId, chapterId, lessonId), payload)
      .then((r) => r.data),

  update: (
    courseId: string,
    chapterId: string,
    lessonId: string,
    resourceId: string,
    payload: ResourceUpdatePayload
  ) =>
    apiClient
      .patch<ResourcePublic>(`${base(courseId, chapterId, lessonId)}/${resourceId}`, payload)
      .then((r) => r.data),

  remove: (courseId: string, chapterId: string, lessonId: string, resourceId: string) =>
    apiClient.delete(`${base(courseId, chapterId, lessonId)}/${resourceId}`).then((r) => r.data),
};
