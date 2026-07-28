import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type WarehouseCreatePayload,
  type WarehouseUpdatePayload,
  warehousesApi,
} from "@/features/inventory/warehouses/api/warehouses-api";

const warehousesKey = ["inventory", "warehouses"] as const;

export function useWarehouses(isActive?: boolean) {
  return useQuery({
    queryKey: [...warehousesKey, isActive],
    queryFn: () => warehousesApi.list(isActive),
  });
}

export function useCreateWarehouse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: WarehouseCreatePayload) => warehousesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: warehousesKey }),
  });
}

export function useUpdateWarehouse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: WarehouseUpdatePayload }) =>
      warehousesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: warehousesKey }),
  });
}
