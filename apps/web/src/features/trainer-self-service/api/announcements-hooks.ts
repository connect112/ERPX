import { useQuery } from "@tanstack/react-query";

import { myAnnouncementsApi } from "@/features/trainer-self-service/api/announcements-api";

export function useMyAnnouncements() {
  return useQuery({
    queryKey: ["announcements", "trainer", "me"],
    queryFn: () => myAnnouncementsApi.myAnnouncements(),
  });
}
