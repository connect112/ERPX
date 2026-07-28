import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AdjustStockPayload,
  type IssueStockPayload,
  type ItemTransactionListParams,
  type ReceiveStockPayload,
  type TransferStockPayload,
  stockApi,
} from "@/features/inventory/stock/api/stock-api";

const stockKeys = {
  all: ["inventory", "stock"] as const,
  itemTransactions: (itemId: string, params: ItemTransactionListParams) =>
    [...stockKeys.all, "transactions", itemId, params] as const,
};

function invalidateStockRelated(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: stockKeys.all });
  queryClient.invalidateQueries({ queryKey: ["inventory", "items"] });
  queryClient.invalidateQueries({ queryKey: ["inventory", "low-stock"] });
}

export function useItemTransactions(itemId: string | undefined, params: ItemTransactionListParams) {
  return useQuery({
    queryKey: stockKeys.itemTransactions(itemId ?? "", params),
    queryFn: () => stockApi.listItemTransactions(itemId as string, params),
    enabled: !!itemId,
    placeholderData: keepPreviousData,
  });
}

export function useReceiveStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReceiveStockPayload) => stockApi.receive(payload),
    onSuccess: () => invalidateStockRelated(queryClient),
  });
}

export function useIssueStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: IssueStockPayload) => stockApi.issue(payload),
    onSuccess: () => invalidateStockRelated(queryClient),
  });
}

export function useAdjustStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdjustStockPayload) => stockApi.adjust(payload),
    onSuccess: () => invalidateStockRelated(queryClient),
  });
}

export function useTransferStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TransferStockPayload) => stockApi.transfer(payload),
    onSuccess: () => invalidateStockRelated(queryClient),
  });
}
