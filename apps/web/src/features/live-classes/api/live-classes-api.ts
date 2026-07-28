import { apiClient } from "@/api/client";

export type LiveClassStatus = "scheduled" | "live" | "completed" | "cancelled";

export interface LiveClassPublic {
  id: string;
  organization_id: string;
  batch_id: string;
  trainer_id: string | null;
  title: string;
  scheduled_at: string;
  duration_minutes: number;
  meeting_link: string;
  recording_url: string | null;
  status: LiveClassStatus;
  created_at: string;
}

export interface LiveClassListResponse {
  items: LiveClassPublic[];
  total: number;
}

export interface LiveClassCreatePayload {
  batch_id: string;
  trainer_id?: string;
  title: string;
  scheduled_at: string;
  duration_minutes?: number;
  meeting_link: string;
}

export const liveClassesApi = {
  listForBatch: (batchId: string) =>
    apiClient
      .get<LiveClassListResponse>("/live-classes", { params: { batch_id: batchId } })
      .then((r) => r.data),

  create: (payload: LiveClassCreatePayload) =>
    apiClient.post<LiveClassPublic>("/live-classes", payload).then((r) => r.data),

  changeStatus: (id: string, status: LiveClassStatus, recordingUrl?: string) =>
    apiClient
      .post<LiveClassPublic>(`/live-classes/${id}/status`, { status, recording_url: recordingUrl })
      .then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/live-classes/${id}`).then((r) => r.data),
};
