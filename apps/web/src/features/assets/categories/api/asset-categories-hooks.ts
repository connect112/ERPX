import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AssetCategoryCreatePayload,
  type AssetCategoryUpdatePayload,
  assetCategoriesApi,
} from "@/features/assets/categories/api/asset-categories-api";

const assetCategoriesKey = ["assets", "categories"] as const;

export function useAssetCategories(isActive?: boolean) {
  return useQuery({
    queryKey: [...assetCategoriesKey, isActive],
    queryFn: () => assetCategoriesApi.list(isActive),
  });
}

export function useCreateAssetCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssetCategoryCreatePayload) => assetCategoriesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assetCategoriesKey }),
  });
}

export function useUpdateAssetCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AssetCategoryUpdatePayload }) =>
      assetCategoriesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assetCategoriesKey }),
  });
}
