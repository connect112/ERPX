import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type BatchCreatePayload,
  type BatchListParams,
  type BatchUpdatePayload,
  batchesApi,
} from "@/features/batches/api/batches-api";

const batchesKeys = {
  all: ["batches"] as const,
  list: (params: BatchListParams) => [...batchesKeys.all, "list", params] as const,
  detail: (id: string) => [...batchesKeys.all, "detail", id] as const,
};

export function useBatchesList(params: BatchListParams = {}) {
  return useQuery({
    queryKey: batchesKeys.list(params),
    queryFn: () => batchesApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useBatch(id: string | undefined) {
  return useQuery({
    queryKey: batchesKeys.detail(id ?? ""),
    queryFn: () => batchesApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BatchCreatePayload) => batchesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: batchesKeys.all }),
  });
}

export function useUpdateBatch(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BatchUpdatePayload) => batchesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: batchesKeys.all }),
  });
}

export function useDeleteBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => batchesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: batchesKeys.all }),
  });
}
