import { apiClient } from "@/api/client";

export interface AnnouncementPublic {
  id: string;
  organization_id: string;
  course_id: string | null;
  created_by_user_id: string | null;
  title: string;
  body: string;
  published_at: string;
}

export interface AnnouncementCreatePayload {
  course_id?: string;
  title: string;
  body: string;
}

export interface AnnouncementUpdatePayload {
  title?: string;
  body?: string;
}

export const announcementsApi = {
  list: (courseId?: string) =>
    apiClient
      .get<AnnouncementPublic[]>("/lms/announcements", { params: { course_id: courseId } })
      .then((r) => r.data),

  create: (payload: AnnouncementCreatePayload) =>
    apiClient.post<AnnouncementPublic>("/lms/announcements", payload).then((r) => r.data),

  update: (id: string, payload: AnnouncementUpdatePayload) =>
    apiClient.patch<AnnouncementPublic>(`/lms/announcements/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/lms/announcements/${id}`).then((r) => r.data),
};
