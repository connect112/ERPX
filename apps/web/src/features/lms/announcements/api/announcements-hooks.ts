import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AnnouncementCreatePayload,
  announcementsApi,
} from "@/features/lms/announcements/api/announcements-api";

const announcementsKey = (courseId?: string) => ["lms", "announcements", courseId ?? "all"] as const;

export function useAnnouncements(courseId?: string) {
  return useQuery({
    queryKey: announcementsKey(courseId),
    queryFn: () => announcementsApi.list(courseId),
  });
}

export function useCreateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AnnouncementCreatePayload) => announcementsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lms", "announcements"] }),
  });
}

export function useDeleteAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => announcementsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["lms", "announcements"] }),
  });
}
