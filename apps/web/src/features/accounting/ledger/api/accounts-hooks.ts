import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AccountCreatePayload,
  type AccountListParams,
  type AccountUpdatePayload,
  accountsApi,
} from "@/features/accounting/ledger/api/accounts-api";

const accountsKeys = {
  all: ["accounting", "accounts"] as const,
  list: (params: AccountListParams) => [...accountsKeys.all, "list", params] as const,
  detail: (id: string) => [...accountsKeys.all, "detail", id] as const,
  balance: (id: string, asOfDate?: string) => [...accountsKeys.all, id, "balance", asOfDate] as const,
};

export function useAccountsList(params: AccountListParams) {
  return useQuery({
    queryKey: accountsKeys.list(params),
    queryFn: () => accountsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useAccount(id: string | undefined) {
  return useQuery({
    queryKey: accountsKeys.detail(id ?? ""),
    queryFn: () => accountsApi.get(id as string),
    enabled: !!id,
  });
}

export function useAccountBalance(id: string, asOfDate?: string) {
  return useQuery({
    queryKey: accountsKeys.balance(id, asOfDate),
    queryFn: () => accountsApi.getBalance(id, asOfDate),
    enabled: !!id,
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AccountCreatePayload) => accountsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountsKeys.all }),
  });
}

export function useUpdateAccount(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AccountUpdatePayload) => accountsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountsKeys.all }),
  });
}
