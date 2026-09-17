import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { attendanceApi } from "@/features/attendance/api/attendance-api";

export function useMyAttendance() {
  return useQuery({
    queryKey: ["attendance", "me"],
    queryFn: () => attendanceApi.myAttendance(),
  });
}

export function useCheckIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => attendanceApi.checkIn(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attendance", "me"] });
    },
  });
}

export function useCheckOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => attendanceApi.checkOut(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attendance", "me"] });
    },
  });
}
