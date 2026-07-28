import { apiClient } from "@/api/client";

export type BackupStatus = "pending" | "running" | "completed" | "failed";

export interface BackupJobPublic {
  id: string;
  triggered_by_user_id: string | null;
  status: BackupStatus;
  storage_key: string | null;
  size_bytes: number | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface BackupJobListResponse {
  items: BackupJobPublic[];
  total: number;
}

export const backupsApi = {
  trigger: () => apiClient.post<BackupJobPublic>("/backups").then((r) => r.data),

  list: (params: { skip?: number; limit?: number }) =>
    apiClient.get<BackupJobListResponse>("/backups", { params }).then((r) => r.data),

  getDownloadUrl: (id: string) =>
    apiClient
      .get<{ download_url: string }>(`/backups/${id}/download-url`)
      .then((r) => r.data.download_url),
};
