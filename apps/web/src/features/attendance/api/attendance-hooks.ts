import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AttendanceListParams,
  type CheckInPayload,
  type CheckOutPayload,
  type EmployeeAttendanceListParams,
  type MarkAttendancePayload,
  type RegularizeAttendancePayload,
  attendanceApi,
} from "@/features/attendance/api/attendance-api";

const attendanceKeys = {
  all: ["attendance"] as const,
  list: (params: AttendanceListParams) => [...attendanceKeys.all, "list", params] as const,
  byEmployee: (employeeId: string, params: EmployeeAttendanceListParams) =>
    [...attendanceKeys.all, "employee", employeeId, params] as const,
  summary: (employeeId: string, year: number, month: number) =>
    [...attendanceKeys.all, "summary", employeeId, year, month] as const,
};

export function useAttendanceList(params: AttendanceListParams) {
  return useQuery({
    queryKey: attendanceKeys.list(params),
    queryFn: () => attendanceApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useEmployeeAttendance(employeeId: string | undefined, params: EmployeeAttendanceListParams) {
  return useQuery({
    queryKey: attendanceKeys.byEmployee(employeeId ?? "", params),
    queryFn: () => attendanceApi.listByEmployee(employeeId as string, params),
    enabled: !!employeeId,
    placeholderData: keepPreviousData,
  });
}

export function useAttendanceSummary(employeeId: string | undefined, year: number, month: number) {
  return useQuery({
    queryKey: attendanceKeys.summary(employeeId ?? "", year, month),
    queryFn: () => attendanceApi.summary(employeeId as string, year, month),
    enabled: !!employeeId,
  });
}

export function useMarkAttendance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MarkAttendancePayload) => attendanceApi.mark(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attendanceKeys.all }),
  });
}

export function useCheckIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CheckInPayload) => attendanceApi.checkIn(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attendanceKeys.all }),
  });
}

export function useCheckOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CheckOutPayload) => attendanceApi.checkOut(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attendanceKeys.all }),
  });
}

export function useRegularizeAttendance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RegularizeAttendancePayload }) =>
      attendanceApi.regularize(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attendanceKeys.all }),
  });
}
