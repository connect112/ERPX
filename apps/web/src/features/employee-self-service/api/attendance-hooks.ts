import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { myAttendanceApi } from "@/features/employee-self-service/api/attendance-api";

const myAttendanceKey = ["attendance", "employee", "me"] as const;

export function useMyAttendance() {
  return useQuery({
    queryKey: myAttendanceKey,
    queryFn: () => myAttendanceApi.myAttendance(),
  });
}

export function useCheckIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => myAttendanceApi.checkIn(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: myAttendanceKey });
    },
  });
}

export function useCheckOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => myAttendanceApi.checkOut(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: myAttendanceKey });
    },
  });
}
