import { useQuery } from "@tanstack/react-query";

import { announcementsApi } from "@/features/announcements/api/announcements-api";

export function useMyAnnouncements() {
  return useQuery({
    queryKey: ["announcements", "trainer", "me"],
    queryFn: () => announcementsApi.myAnnouncements(),
  });
}
