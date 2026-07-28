import { apiClient } from "@/api/client";
import type { LabDifficulty } from "@/features/pentrix/labs/schemas/lab-schemas";

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

export interface ChallengeCreatePayload {
  lab_id?: string;
  title: string;
  description: string;
  category: string;
  difficulty: LabDifficulty;
  points?: number;
}

export interface ChallengeUpdatePayload {
  title?: string;
  description?: string;
  category?: string;
  difficulty?: LabDifficulty;
  points?: number;
  is_active?: boolean;
}

export const challengesApi = {
  list: (category?: string) =>
    apiClient
      .get<ChallengePublic[]>("/pentrix/challenges", { params: { category } })
      .then((r) => r.data),

  get: (id: string) => apiClient.get<ChallengePublic>(`/pentrix/challenges/${id}`).then((r) => r.data),

  create: (payload: ChallengeCreatePayload) =>
    apiClient.post<ChallengePublic>("/pentrix/challenges", payload).then((r) => r.data),

  update: (id: string, payload: ChallengeUpdatePayload) =>
    apiClient.patch<ChallengePublic>(`/pentrix/challenges/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/pentrix/challenges/${id}`).then((r) => r.data),
};
