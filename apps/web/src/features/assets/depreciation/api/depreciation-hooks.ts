import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type DepreciationRunGeneratePayload,
  type DepreciationRunListParams,
  depreciationApi,
} from "@/features/assets/depreciation/api/depreciation-api";

const runsKeys = {
  all: ["assets", "depreciation-runs"] as const,
  list: (params: DepreciationRunListParams) => [...runsKeys.all, "list", params] as const,
  detail: (id: string) => [...runsKeys.all, "detail", id] as const,
  entries: (id: string) => [...runsKeys.all, id, "entries"] as const,
};

export function useDepreciationRuns(params: DepreciationRunListParams) {
  return useQuery({
    queryKey: runsKeys.list(params),
    queryFn: () => depreciationApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useDepreciationRun(id: string | undefined) {
  return useQuery({
    queryKey: runsKeys.detail(id ?? ""),
    queryFn: () => depreciationApi.get(id as string),
    enabled: !!id,
  });
}

export function useDepreciationEntries(runId: string | undefined) {
  return useQuery({
    queryKey: runsKeys.entries(runId ?? ""),
    queryFn: () => depreciationApi.listEntries(runId as string),
    enabled: !!runId,
  });
}

export function useGenerateDepreciationRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DepreciationRunGeneratePayload) => depreciationApi.generate(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runsKeys.all }),
  });
}

export function usePostDepreciationRun(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => depreciationApi.post(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: runsKeys.all });
      queryClient.invalidateQueries({ queryKey: ["assets", "assets"] });
    },
  });
}

export function useCancelDepreciationRun(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => depreciationApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: runsKeys.all }),
  });
}
