import { apiClient } from "@/api/client";

export type NotificationType = "info" | "success" | "warning" | "error" | "action_required";

export interface NotificationPublic {
  id: string;
  organization_id: string;
  user_id: string;
  title: string;
  body: string | null;
  notification_type: NotificationType;
  link_url: string | null;
  source: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationPublic[];
  total: number;
}

export interface BroadcastPayload {
  title: string;
  body?: string;
  notification_type: NotificationType;
  link_url?: string;
}

export const notificationsApi = {
  list: (params: { unread_only?: boolean; skip?: number; limit?: number }) =>
    apiClient.get<NotificationListResponse>("/notifications/me", { params }).then((r) => r.data),

  unreadCount: () =>
    apiClient.get<{ unread_count: number }>("/notifications/me/unread-count").then((r) => r.data.unread_count),

  markRead: (id: string) =>
    apiClient.post<NotificationPublic>(`/notifications/me/${id}/read`).then((r) => r.data),

  markAllRead: () => apiClient.post("/notifications/me/read-all").then((r) => r.data),

  broadcast: (payload: BroadcastPayload) =>
    apiClient.post<{ notified_count: number }>("/notifications/broadcast", payload).then((r) => r.data),
};
