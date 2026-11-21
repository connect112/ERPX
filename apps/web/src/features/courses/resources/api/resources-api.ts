import { apiClient } from "@/api/client";
import type { ResourceType } from "@/features/courses/resources/schemas/resource-schemas";

export interface ResourcePublic {
  id: string;
  lesson_id: string;
  title: string;
  resource_type: ResourceType;
  file_url: string;
  is_downloadable: boolean;
  /** an uploaded file (downloaded through an authenticated link) rather than a link */
  is_upload: boolean;
  original_filename: string | null;
  size_bytes: number | null;
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

  upload: (courseId: string, chapterId: string, lessonId: string, input: { file: File; title: string; resourceType: ResourceType; isDownloadable: boolean }) => {
    const form = new FormData();
    form.append("file", input.file);
    form.append("title", input.title);
    form.append("resource_type", input.resourceType);
    form.append("is_downloadable", String(input.isDownloadable));
    return apiClient.post<ResourcePublic>(`${base(courseId, chapterId, lessonId)}/upload`, form).then((r) => r.data);
  },

  /** A short-lived link to an uploaded file; the server checks who is asking each time. */
  downloadLink: (courseId: string, chapterId: string, lessonId: string, resourceId: string) =>
    apiClient.get<{ url: string; filename: string }>(`${base(courseId, chapterId, lessonId)}/${resourceId}/download`).then((r) => r.data),

  remove: (courseId: string, chapterId: string, lessonId: string, resourceId: string) =>
    apiClient.delete(`${base(courseId, chapterId, lessonId)}/${resourceId}`).then((r) => r.data),
};
