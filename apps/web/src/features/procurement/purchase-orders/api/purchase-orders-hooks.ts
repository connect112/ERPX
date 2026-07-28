import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type PurchaseOrderCreatePayload,
  type PurchaseOrderListParams,
  type PurchaseOrderUpdatePayload,
  purchaseOrdersApi,
} from "@/features/procurement/purchase-orders/api/purchase-orders-api";

const purchaseOrdersKeys = {
  all: ["procurement", "purchase-orders"] as const,
  list: (params: PurchaseOrderListParams) => [...purchaseOrdersKeys.all, "list", params] as const,
  detail: (id: string) => [...purchaseOrdersKeys.all, "detail", id] as const,
};

export function usePurchaseOrdersList(params: PurchaseOrderListParams) {
  return useQuery({
    queryKey: purchaseOrdersKeys.list(params),
    queryFn: () => purchaseOrdersApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function usePurchaseOrder(id: string | undefined) {
  return useQuery({
    queryKey: purchaseOrdersKeys.detail(id ?? ""),
    queryFn: () => purchaseOrdersApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PurchaseOrderCreatePayload) => purchaseOrdersApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchaseOrdersKeys.all }),
  });
}

export function useUpdatePurchaseOrder(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PurchaseOrderUpdatePayload) => purchaseOrdersApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchaseOrdersKeys.all }),
  });
}

export function useSendPurchaseOrder(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => purchaseOrdersApi.send(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchaseOrdersKeys.all }),
  });
}

export function useCancelPurchaseOrder(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => purchaseOrdersApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchaseOrdersKeys.all }),
  });
}
