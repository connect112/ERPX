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

export const announcementsApi = {
  // Ownership-gated (see modules/lms/announcements/routes.py's
  // list_my_announcements_as_student) — every org-wide announcement plus
  // every one scoped to a course this student is enrolled in. No
  // lms.announcements.view permission needed; admin-only for posting.
  myAnnouncements: () =>
    apiClient.get<AnnouncementPublic[]>("/lms/announcements/me").then((r) => r.data),
};
