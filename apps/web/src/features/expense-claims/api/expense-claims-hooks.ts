import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type ExpenseClaimListParams, expenseClaimsApi } from "@/features/expense-claims/api/expense-claims-api";

const claimsKeys = {
  all: ["expense-claims"] as const,
  list: (params: ExpenseClaimListParams) => [...claimsKeys.all, "list", params] as const,
};

export function useExpenseClaims(params: ExpenseClaimListParams) {
  return useQuery({
    queryKey: claimsKeys.list(params),
    queryFn: () => expenseClaimsApi.list(params),
  });
}

export function useApproveExpenseClaim() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => expenseClaimsApi.approve(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: claimsKeys.all }),
  });
}

export function useRejectExpenseClaim() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, rejectionReason }: { id: string; rejectionReason: string }) =>
      expenseClaimsApi.reject(id, rejectionReason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: claimsKeys.all }),
  });
}
