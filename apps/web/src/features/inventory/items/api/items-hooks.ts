import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ItemCreatePayload,
  type ItemListParams,
  type ItemUpdatePayload,
  itemsApi,
} from "@/features/inventory/items/api/items-api";

const itemsKeys = {
  all: ["inventory", "items"] as const,
  list: (params: ItemListParams) => [...itemsKeys.all, "list", params] as const,
  detail: (id: string) => [...itemsKeys.all, "detail", id] as const,
  stockLevel: (id: string, warehouseId?: string) => [...itemsKeys.all, id, "stock-level", warehouseId] as const,
};
const lowStockKey = (warehouseId?: string) => ["inventory", "low-stock", warehouseId] as const;

export function useItemsList(params: ItemListParams) {
  return useQuery({
    queryKey: itemsKeys.list(params),
    queryFn: () => itemsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useItem(id: string | undefined) {
  return useQuery({
    queryKey: itemsKeys.detail(id ?? ""),
    queryFn: () => itemsApi.get(id as string),
    enabled: !!id,
  });
}

export function useItemStockLevel(id: string | undefined, warehouseId?: string) {
  return useQuery({
    queryKey: itemsKeys.stockLevel(id ?? "", warehouseId),
    queryFn: () => itemsApi.stockLevel(id as string, warehouseId),
    enabled: !!id,
  });
}

export function useLowStockItems(warehouseId?: string) {
  return useQuery({
    queryKey: lowStockKey(warehouseId),
    queryFn: () => itemsApi.lowStock(warehouseId),
  });
}

export function useCreateItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ItemCreatePayload) => itemsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: itemsKeys.all }),
  });
}

export function useUpdateItem(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ItemUpdatePayload) => itemsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: itemsKeys.all }),
  });
}
