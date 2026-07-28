import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type LiveClassCreatePayload,
  type LiveClassStatus,
  liveClassesApi,
} from "@/features/live-classes/api/live-classes-api";

const liveClassesKeys = {
  all: ["live-classes"] as const,
  forBatch: (batchId: string) => [...liveClassesKeys.all, "batch", batchId] as const,
};

export function useLiveClassesForBatch(batchId: string) {
  return useQuery({
    queryKey: liveClassesKeys.forBatch(batchId),
    queryFn: () => liveClassesApi.listForBatch(batchId),
    enabled: !!batchId,
  });
}

export function useCreateLiveClass(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LiveClassCreatePayload) => liveClassesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: liveClassesKeys.forBatch(batchId) }),
  });
}

export function useChangeLiveClassStatus(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, recordingUrl }: { id: string; status: LiveClassStatus; recordingUrl?: string }) =>
      liveClassesApi.changeStatus(id, status, recordingUrl),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: liveClassesKeys.forBatch(batchId) }),
  });
}

export function useDeleteLiveClass(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => liveClassesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: liveClassesKeys.forBatch(batchId) }),
  });
}
