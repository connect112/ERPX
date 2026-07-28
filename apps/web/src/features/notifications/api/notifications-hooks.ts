import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type BroadcastPayload, notificationsApi } from "@/features/notifications/api/notifications-api";

const notificationsKeys = {
  all: ["notifications"] as const,
  list: (params: { unread_only?: boolean; skip?: number; limit?: number }) =>
    [...notificationsKeys.all, "list", params] as const,
  unreadCount: () => [...notificationsKeys.all, "unread-count"] as const,
};

export function useNotificationsList(params: { unread_only?: boolean; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: notificationsKeys.list(params),
    queryFn: () => notificationsApi.list(params),
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: notificationsKeys.unreadCount(),
    queryFn: () => notificationsApi.unreadCount(),
    refetchInterval: 30_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKeys.all }),
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKeys.all }),
  });
}

export function useBroadcastNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BroadcastPayload) => notificationsApi.broadcast(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKeys.all }),
  });
}
