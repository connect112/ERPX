import { apiClient } from "@/api/client";

export type LabDifficulty = "easy" | "medium" | "hard" | "insane";

export interface LabPublic {
  id: string;
  organization_id: string;
  title: string;
  slug: string;
  description: string | null;
  category: string;
  difficulty: LabDifficulty;
  environment_image: string;
  points: number;
  default_duration_minutes: number;
  is_active: boolean;
  created_at: string;
}

export type LabInstanceStatus = "provisioning" | "running" | "stopped" | "expired" | "failed";

export interface LabInstancePublic {
  id: string;
  lab_id: string;
  student_id: string;
  environment_ref: string | null;
  access_endpoint: string | null;
  status: LabInstanceStatus;
  started_at: string;
  expires_at: string;
  stopped_at: string | null;
}

export interface ChallengePublic {
  id: string;
  organization_id: string;
  lab_id: string | null;
  title: string;
  description: string;
  category: string;
  difficulty: LabDifficulty;
  points: number;
  is_active: boolean;
  created_at: string;
}

export interface SolvePublic {
  id: string;
  challenge_id: string;
  student_id: string;
  points_awarded: number;
  solved_at: string;
}

export interface SubmissionResultResponse {
  correct: boolean;
  already_solved: boolean;
  points_awarded: number;
}

export const pentrixApi = {
  listLabs: () => apiClient.get<LabPublic[]>("/pentrix/labs").then((r) => r.data),

  launchLab: (labId: string, studentId: string) =>
    apiClient
      .post<LabInstancePublic>(`/pentrix/labs/${labId}/launch`, { student_id: studentId })
      .then((r) => r.data),

  stopInstance: (instanceId: string) =>
    apiClient.post<LabInstancePublic>(`/pentrix/instances/${instanceId}/stop`).then((r) => r.data),

  myInstances: (studentId: string) =>
    apiClient
      .get<LabInstancePublic[]>(`/pentrix/students/${studentId}/instances`)
      .then((r) => r.data),

  listChallenges: () => apiClient.get<ChallengePublic[]>("/pentrix/challenges").then((r) => r.data),

  mySolves: (studentId: string) =>
    apiClient.get<SolvePublic[]>(`/pentrix/students/${studentId}/solves`).then((r) => r.data),

  submitFlag: (challengeId: string, studentId: string, flagValue: string) =>
    apiClient
      .post<SubmissionResultResponse>(`/pentrix/challenges/${challengeId}/submit`, {
        student_id: studentId,
        flag_value: flagValue,
      })
      .then((r) => r.data),
};
