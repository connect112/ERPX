import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type BankAccountCreatePayload,
  type BankAccountUpdatePayload,
  type BankTransactionCreatePayload,
  bankApi,
} from "@/features/accounting/bank/api/bank-api";

const accountsKey = ["accounting", "bank", "accounts"] as const;
const accountDetailKey = (id: string) => [...accountsKey, "detail", id] as const;
const balanceKey = (id: string, asOfDate?: string) => [...accountsKey, id, "balance", asOfDate] as const;
const transactionsKey = (id: string) => [...accountsKey, id, "transactions"] as const;

export function useBankAccounts(isActive?: boolean) {
  return useQuery({
    queryKey: [...accountsKey, isActive],
    queryFn: () => bankApi.listAccounts(isActive),
  });
}

export function useBankAccount(id: string | undefined) {
  return useQuery({
    queryKey: accountDetailKey(id ?? ""),
    queryFn: () => bankApi.getAccount(id as string),
    enabled: !!id,
  });
}

export function useBankAccountBalance(id: string, asOfDate?: string) {
  return useQuery({
    queryKey: balanceKey(id, asOfDate),
    queryFn: () => bankApi.getBalance(id, asOfDate),
    enabled: !!id,
  });
}

export function useCreateBankAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BankAccountCreatePayload) => bankApi.createAccount(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountsKey }),
  });
}

export function useUpdateBankAccount(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BankAccountUpdatePayload) => bankApi.updateAccount(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: accountsKey }),
  });
}

export function useBankTransactions(bankAccountId: string) {
  return useQuery({
    queryKey: transactionsKey(bankAccountId),
    queryFn: () => bankApi.listTransactions(bankAccountId),
    enabled: !!bankAccountId,
  });
}

export function useCreateBankTransaction(bankAccountId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BankTransactionCreatePayload) =>
      bankApi.createTransaction(bankAccountId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: transactionsKey(bankAccountId) });
      queryClient.invalidateQueries({ queryKey: [...accountsKey, bankAccountId, "balance"] });
    },
  });
}

export function useReconcileTransaction(bankAccountId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (transactionId: string) => bankApi.reconcileTransaction(transactionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: transactionsKey(bankAccountId) }),
  });
}
