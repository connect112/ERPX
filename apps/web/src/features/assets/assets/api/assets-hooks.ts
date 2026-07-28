import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AssetCreatePayload,
  type AssetListParams,
  type AssetUpdatePayload,
  type DisposeAssetPayload,
  assetsApi,
} from "@/features/assets/assets/api/assets-api";

const assetsKeys = {
  all: ["assets", "assets"] as const,
  list: (params: AssetListParams) => [...assetsKeys.all, "list", params] as const,
  detail: (id: string) => [...assetsKeys.all, "detail", id] as const,
  netBookValue: (id: string, asOfDate?: string) => [...assetsKeys.all, id, "nbv", asOfDate] as const,
};

export function useAssetsList(params: AssetListParams) {
  return useQuery({
    queryKey: assetsKeys.list(params),
    queryFn: () => assetsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useAsset(id: string | undefined) {
  return useQuery({
    queryKey: assetsKeys.detail(id ?? ""),
    queryFn: () => assetsApi.get(id as string),
    enabled: !!id,
  });
}

export function useAssetNetBookValue(id: string | undefined, asOfDate?: string) {
  return useQuery({
    queryKey: assetsKeys.netBookValue(id ?? "", asOfDate),
    queryFn: () => assetsApi.netBookValue(id as string, asOfDate),
    enabled: !!id,
  });
}

export function useCreateAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssetCreatePayload) => assetsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assetsKeys.all }),
  });
}

export function useUpdateAsset(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssetUpdatePayload) => assetsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assetsKeys.all }),
  });
}

export function useDisposeAsset(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DisposeAssetPayload) => assetsApi.dispose(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assetsKeys.all }),
  });
}
