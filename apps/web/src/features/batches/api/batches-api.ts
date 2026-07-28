import { apiClient } from "@/api/client";

export type BatchStatus = "upcoming" | "ongoing" | "completed" | "cancelled";

export interface BatchPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  course_id: string;
  trainer_id: string | null;
  name: string;
  code: string;
  status: BatchStatus;
  capacity: number | null;
  start_date: string;
  end_date: string | null;
  created_at: string;
}

export interface BatchListResponse {
  items: BatchPublic[];
  total: number;
}

export interface BatchListParams {
  course_id?: string;
  status?: BatchStatus;
  skip?: number;
  limit?: number;
}

export interface BatchCreatePayload {
  course_id: string;
  branch_id?: string;
  trainer_id?: string;
  name: string;
  code: string;
  capacity?: number;
  start_date: string;
  end_date?: string;
}

export type BatchUpdatePayload = Partial<Omit<BatchCreatePayload, "course_id" | "code">> & {
  status?: BatchStatus;
};

export const batchesApi = {
  list: (params: BatchListParams) =>
    apiClient.get<BatchListResponse>("/batches", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<BatchPublic>(`/batches/${id}`).then((r) => r.data),

  create: (payload: BatchCreatePayload) =>
    apiClient.post<BatchPublic>("/batches", payload).then((r) => r.data),

  update: (id: string, payload: BatchUpdatePayload) =>
    apiClient.patch<BatchPublic>(`/batches/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/batches/${id}`).then((r) => r.data),
};
