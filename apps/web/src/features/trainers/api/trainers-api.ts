import { apiClient } from "@/api/client";

export interface TrainerPublic {
  id: string;
  organization_id: string;
  employee_id: string;
  employee_name: string;
  employee_email: string | null;
  specializations: string | null;
  bio: string | null;
  max_weekly_hours: number | null;
  is_active: boolean;
  created_at: string;
}

export interface TrainerListResponse {
  items: TrainerPublic[];
  total: number;
}

export interface TrainerCreatePayload {
  employee_id: string;
  specializations?: string;
  bio?: string;
  max_weekly_hours?: number;
}

export type TrainerUpdatePayload = Partial<Omit<TrainerCreatePayload, "employee_id">> & {
  is_active?: boolean;
};

export const trainersApi = {
  list: (params: { skip?: number; limit?: number }) =>
    apiClient.get<TrainerListResponse>("/trainers", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<TrainerPublic>(`/trainers/${id}`).then((r) => r.data),

  create: (payload: TrainerCreatePayload) =>
    apiClient.post<TrainerPublic>("/trainers", payload).then((r) => r.data),

  update: (id: string, payload: TrainerUpdatePayload) =>
    apiClient.patch<TrainerPublic>(`/trainers/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/trainers/${id}`).then((r) => r.data),
};
