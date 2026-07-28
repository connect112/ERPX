import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ExpenseCreatePayload,
  type ExpenseListParams,
  expensesApi,
} from "@/features/accounting/expenses/api/expenses-api";

const expensesKeys = {
  all: ["accounting", "expenses"] as const,
  list: (params: ExpenseListParams) => [...expensesKeys.all, "list", params] as const,
  detail: (id: string) => [...expensesKeys.all, "detail", id] as const,
};

export function useExpensesList(params: ExpenseListParams) {
  return useQuery({
    queryKey: expensesKeys.list(params),
    queryFn: () => expensesApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useExpense(id: string | undefined) {
  return useQuery({
    queryKey: expensesKeys.detail(id ?? ""),
    queryFn: () => expensesApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExpenseCreatePayload) => expensesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expensesKeys.all }),
  });
}

export function useApproveExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => expensesApi.approve(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expensesKeys.all }),
  });
}

export function useRejectExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, rejectionReason }: { id: string; rejectionReason: string }) =>
      expensesApi.reject(id, rejectionReason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expensesKeys.all }),
  });
}

export function useCancelExpense() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => expensesApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: expensesKeys.all }),
  });
}
