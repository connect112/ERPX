import { apiClient } from "@/api/client";

export interface LearningPathPublic {
  id: string;
  organization_id: string;
  title: string;
  slug: string;
  description: string | null;
  created_at: string;
}

export interface LearningPathCoursePublic {
  id: string;
  course_id: string;
  order_index: number;
}

export interface LearningPathCreatePayload {
  title: string;
  slug: string;
  description?: string;
}

export interface LearningPathUpdatePayload {
  title?: string;
  description?: string;
}

export interface AddCourseToPathPayload {
  course_id: string;
  order_index: number;
}

export const learningPathsApi = {
  list: () => apiClient.get<LearningPathPublic[]>("/courses/learning-paths").then((r) => r.data),

  get: (id: string) =>
    apiClient.get<LearningPathPublic>(`/courses/learning-paths/${id}`).then((r) => r.data),

  create: (payload: LearningPathCreatePayload) =>
    apiClient.post<LearningPathPublic>("/courses/learning-paths", payload).then((r) => r.data),

  update: (id: string, payload: LearningPathUpdatePayload) =>
    apiClient
      .patch<LearningPathPublic>(`/courses/learning-paths/${id}`, payload)
      .then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/courses/learning-paths/${id}`).then((r) => r.data),

  listCourses: (id: string) =>
    apiClient
      .get<LearningPathCoursePublic[]>(`/courses/learning-paths/${id}/courses`)
      .then((r) => r.data),

  addCourse: (id: string, payload: AddCourseToPathPayload) =>
    apiClient
      .post<LearningPathCoursePublic>(`/courses/learning-paths/${id}/courses`, payload)
      .then((r) => r.data),

  removeCourse: (id: string, courseId: string) =>
    apiClient.delete(`/courses/learning-paths/${id}/courses/${courseId}`).then((r) => r.data),
};
