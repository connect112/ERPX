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
  });
}

export function useJoinLiveClass() {
  return useMutation({
    mutationFn: (id: string) => myScheduleApi.joinLiveClass(id),
  });
}
