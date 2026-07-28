import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ReceiptCreatePayload,
  type ReceiptListParams,
  receiptsApi,
} from "@/features/accounting/receipts/api/receipts-api";

const receiptsKeys = {
  all: ["accounting", "receipts"] as const,
  list: (params: ReceiptListParams) => [...receiptsKeys.all, "list", params] as const,
};

export function useReceiptsList(params: ReceiptListParams) {
  return useQuery({
    queryKey: receiptsKeys.list(params),
    queryFn: () => receiptsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReceiptCreatePayload) => receiptsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: receiptsKeys.all }),
  });
}

export function useVoidReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => receiptsApi.void(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: receiptsKeys.all }),
  });
}
