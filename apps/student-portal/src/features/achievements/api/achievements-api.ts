import { apiClient } from "@/api/client";

export interface AchievementPublic {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  criteria_type: string;
  criteria_value: number;
  created_at: string;
}

export interface StudentAchievementPublic {
  id: string;
  student_id: string;
  achievement_id: string;
  awarded_at: string;
}

export interface CertificationPublic {
  id: string;
  student_id: string;
  track_name: string;
  certificate_number: string;
  points_at_issuance: number;
  issued_at: string;
}

export const achievementsApi = {
  // The full achievement catalog — StudentAchievementPublic only carries an
  // achievement_id, so this is joined against client-side to show name/
  // description. Both endpoints are permission-gated the same way
  // (pentrix.achievements.view), which the student role holds.
  catalog: () => apiClient.get<AchievementPublic[]>("/pentrix/achievements").then((r) => r.data),

  mine: (studentId: string) =>
    apiClient
      .get<StudentAchievementPublic[]>(`/pentrix/achievements/students/${studentId}`)
      .then((r) => r.data),

  myCertifications: (studentId: string) =>
    apiClient
      .get<CertificationPublic[]>(`/pentrix/certifications/students/${studentId}`)
      .then((r) => r.data),
};
