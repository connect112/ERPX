import { apiClient } from "@/api/client";
import type { LabDifficulty } from "@/features/pentrix/labs/schemas/lab-schemas";

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

export interface LabCreatePayload {
  title: string;
  slug: string;
  description?: string;
  category: string;
  difficulty: LabDifficulty;
  environment_image: string;
  points?: number;
  default_duration_minutes?: number;
}

export interface LabUpdatePayload {
  title?: string;
  description?: string;
  category?: string;
  difficulty?: LabDifficulty;
  environment_image?: string;
  points?: number;
  default_duration_minutes?: number;
  is_active?: boolean;
}

export const labsApi = {
  list: () => apiClient.get<LabPublic[]>("/pentrix/labs").then((r) => r.data),

  get: (id: string) => apiClient.get<LabPublic>(`/pentrix/labs/${id}`).then((r) => r.data),

  create: (payload: LabCreatePayload) =>
    apiClient.post<LabPublic>("/pentrix/labs", payload).then((r) => r.data),

  update: (id: string, payload: LabUpdatePayload) =>
    apiClient.patch<LabPublic>(`/pentrix/labs/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/pentrix/labs/${id}`).then((r) => r.data),
};
