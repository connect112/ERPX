import { useMutation, useQuery } from "@tanstack/react-query";

import { scheduleApi } from "@/features/schedule/api/schedule-api";

export function useMyTimetable() {
  return useQuery({
    queryKey: ["timetable", "me"],
    queryFn: () => scheduleApi.myTimetable(),
  });
}

export function useMyLiveClasses() {
  return useQuery({
    queryKey: ["live-classes", "me"],
    queryFn: () => scheduleApi.myLiveClasses(),
  });
}

export function useJoinLiveClass() {
  return useMutation({
    mutationFn: (id: string) => scheduleApi.joinLiveClass(id),
  });
}
