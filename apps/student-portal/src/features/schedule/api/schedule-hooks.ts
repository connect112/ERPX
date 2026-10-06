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
    // The Join button only appears once the trainer has joined, which happens
    // while the student is already looking at this list. Poll (foreground
    // tab only) so it shows up without a manual reload.
    refetchInterval: 10_000,
  });
}

export function useJoinLiveClass() {
  return useMutation({
    mutationFn: (id: string) => scheduleApi.joinLiveClass(id),
  });
}
