import { apiClient } from "@/api/client";

export interface BadgePublic {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  icon_url: string | null;
  created_at: string;
}

export interface StudentBadgePublic {
  id: string;
  student_id: string;
  badge_id: string;
  awarded_at: string;
}

export interface BadgeCreatePayload {
  name: string;
  description?: string;
  icon_url?: string;
}

export const badgesApi = {
  list: () => apiClient.get<BadgePublic[]>("/lms/badges").then((r) => r.data),

  create: (payload: BadgeCreatePayload) =>
    apiClient.post<BadgePublic>("/lms/badges", payload).then((r) => r.data),

  award: (studentId: string, badgeId: string) =>
    apiClient
      .post<StudentBadgePublic>("/lms/badges/award", { student_id: studentId, badge_id: badgeId })
      .then((r) => r.data),

  listForStudent: (studentId: string) =>
    apiClient
      .get<StudentBadgePublic[]>(`/lms/badges/by-student/${studentId}`)
      .then((r) => r.data),
};
