import { useMutation, useQuery } from "@tanstack/react-query";

import { myScheduleApi } from "@/features/student-self-service/api/schedule-api";

export function useMyTimetable() {
  return useQuery({
    queryKey: ["timetable", "me"],
    queryFn: () => myScheduleApi.myTimetable(),
  });
}

export function useMyLiveClasses() {
  return useQuery({
    queryKey: ["live-classes", "me"],
    queryFn: () => myScheduleApi.myLiveClasses(),
    // The Join button only appears once the trainer has joined, which happens
    // while the student is already looking at this list. Poll (foreground
    // tab only) so it shows up without a manual reload.
    refetchInterval: 10_000,
  });
}

export function useJoinLiveClass() {
  return useMutation({
    mutationFn: (id: string) => myScheduleApi.joinLiveClass(id),
  });
}
