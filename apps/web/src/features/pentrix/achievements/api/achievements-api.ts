import { apiClient } from "@/api/client";
import type { AchievementCriteriaType } from "@/features/pentrix/achievements/schemas/achievement-schemas";

export interface AchievementPublic {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  criteria_type: AchievementCriteriaType;
  criteria_value: number;
  created_at: string;
}

export interface StudentAchievementPublic {
  id: string;
  student_id: string;
  achievement_id: string;
  awarded_at: string;
}

export interface AchievementCreatePayload {
  name: string;
  description?: string;
  criteria_type: AchievementCriteriaType;
  criteria_value: number;
}

export const achievementsApi = {
  list: () => apiClient.get<AchievementPublic[]>("/pentrix/achievements").then((r) => r.data),

  create: (payload: AchievementCreatePayload) =>
    apiClient.post<AchievementPublic>("/pentrix/achievements", payload).then((r) => r.data),

  listForStudent: (studentId: string) =>
    apiClient
      .get<StudentAchievementPublic[]>(`/pentrix/achievements/students/${studentId}`)
      .then((r) => r.data),
};
