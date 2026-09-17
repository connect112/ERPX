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
  // list_my_announcements_as_trainer) — every org-wide announcement plus
  // every one scoped to a course this trainer teaches a batch of. No
  // lms.announcements.view permission needed; admin-only for posting.
  myAnnouncements: () =>
    apiClient.get<AnnouncementPublic[]>("/lms/announcements/trainer/me").then((r) => r.data),
};
