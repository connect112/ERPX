import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { leaveApi } from "@/features/leave/api/leave-api";

const applicationsKey = ["leave", "applications", "me"] as const;
const balancesKey = (year: number) => ["leave", "balances", "me", year] as const;

export function useMyLeaveTypes() {
  return useQuery({
    queryKey: ["leave", "types", "me"],
    queryFn: () => leaveApi.myLeaveTypes(),
  });
}

export function useMyLeaveApplications() {
  return useQuery({
    queryKey: applicationsKey,
    queryFn: () => leaveApi.myApplications(),
  });
}

export function useMyLeaveBalances(year: number) {
  return useQuery({
    queryKey: balancesKey(year),
    queryFn: () => leaveApi.myBalances(year),
  });
}

export function useApplyLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { leave_type_id: string; start_date: string; end_date: string; reason: string }) =>
      leaveApi.apply(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationsKey });
      queryClient.invalidateQueries({ queryKey: ["leave", "balances", "me"] });
    },
  });
}

export function useCancelLeaveApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leaveApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: applicationsKey });
      queryClient.invalidateQueries({ queryKey: ["leave", "balances", "me"] });
    },
  });
}
