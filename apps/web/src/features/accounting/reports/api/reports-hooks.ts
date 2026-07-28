import { useQuery } from "@tanstack/react-query";

import { reportsApi } from "@/features/accounting/reports/api/reports-api";

export function useTrialBalance(asOfDate: string) {
  return useQuery({
    queryKey: ["accounting", "reports", "trial-balance", asOfDate],
    queryFn: () => reportsApi.trialBalance(asOfDate),
    enabled: !!asOfDate,
  });
}

export function useProfitAndLoss(periodFrom: string, periodTo: string) {
  return useQuery({
    queryKey: ["accounting", "reports", "profit-and-loss", periodFrom, periodTo],
    queryFn: () => reportsApi.profitAndLoss(periodFrom, periodTo),
    enabled: !!periodFrom && !!periodTo,
  });
}

export function useBalanceSheet(asOfDate: string) {
  return useQuery({
    queryKey: ["accounting", "reports", "balance-sheet", asOfDate],
    queryFn: () => reportsApi.balanceSheet(asOfDate),
    enabled: !!asOfDate,
  });
}

export function useARAging(asOfDate: string) {
  return useQuery({
    queryKey: ["accounting", "reports", "ar-aging", asOfDate],
    queryFn: () => reportsApi.arAging(asOfDate),
    enabled: !!asOfDate,
  });
}

export function useAPAging(asOfDate: string) {
  return useQuery({
    queryKey: ["accounting", "reports", "ap-aging", asOfDate],
    queryFn: () => reportsApi.apAging(asOfDate),
    enabled: !!asOfDate,
  });
}
