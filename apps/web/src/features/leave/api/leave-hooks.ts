import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type LeaveApplicationCreatePayload,
  type LeaveApplicationListParams,
  type LeaveTypeCreatePayload,
  type LeaveTypeUpdatePayload,
  leaveApi,
} from "@/features/leave/api/leave-api";

const leaveTypesKey = ["leave", "types"] as const;
const applicationsKeys = {
  all: ["leave", "applications"] as const,
  list: (params: LeaveApplicationListParams) => [...applicationsKeys.all, "list", params] as const,
  byEmployee: (employeeId: string, params: LeaveApplicationListParams) =>
    [...applicationsKeys.all, "employee", employeeId, params] as const,
};
const balancesKey = (employeeId: string, year: number) =>
  ["leave", "balances", employeeId, year] as const;

export function useLeaveTypes(isActive?: boolean) {
  return useQuery({
    queryKey: [...leaveTypesKey, isActive],
    queryFn: () => leaveApi.listTypes(isActive),
  });
}

export function useCreateLeaveType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LeaveTypeCreatePayload) => leaveApi.createType(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: leaveTypesKey }),
  });
}

export function useUpdateLeaveType() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: LeaveTypeUpdatePayload }) =>
      leaveApi.updateType(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: leaveTypesKey }),
  });
}

export function useLeaveApplications(params: LeaveApplicationListParams) {
  return useQuery({
    queryKey: applicationsKeys.list(params),
    queryFn: () => leaveApi.listApplications(params),
    placeholderData: keepPreviousData,
  });
}

export function useEmployeeLeaveApplications(
  employeeId: string | undefined,
  params: LeaveApplicationListParams
) {
  return useQuery({
    queryKey: applicationsKeys.byEmployee(employeeId ?? "", params),
    queryFn: () => leaveApi.listApplicationsByEmployee(employeeId as string, params),
    enabled: !!employeeId,
    placeholderData: keepPreviousData,
  });
}

export function useApplyLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LeaveApplicationCreatePayload) => leaveApi.apply(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationsKeys.all }),
  });
}

export function useApproveLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leaveApi.approve(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationsKeys.all }),
  });
}

export function useRejectLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, rejectionReason }: { id: string; rejectionReason: string }) =>
      leaveApi.reject(id, rejectionReason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationsKeys.all }),
  });
}

export function useCancelLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leaveApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: applicationsKeys.all }),
  });
}

export function useLeaveBalances(employeeId: string | undefined, year: number) {
  return useQuery({
    queryKey: balancesKey(employeeId ?? "", year),
    queryFn: () => leaveApi.balances(employeeId as string, year),
    enabled: !!employeeId,
  });
}
