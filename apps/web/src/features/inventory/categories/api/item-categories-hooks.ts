import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ItemCategoryCreatePayload,
  type ItemCategoryUpdatePayload,
  itemCategoriesApi,
} from "@/features/inventory/categories/api/item-categories-api";

const itemCategoriesKey = ["inventory", "categories"] as const;

export function useItemCategories(isActive?: boolean) {
  return useQuery({
    queryKey: [...itemCategoriesKey, isActive],
    queryFn: () => itemCategoriesApi.list(isActive),
  });
}

export function useCreateItemCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ItemCategoryCreatePayload) => itemCategoriesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: itemCategoriesKey }),
  });
}

export function useUpdateItemCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ItemCategoryUpdatePayload }) =>
      itemCategoriesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: itemCategoriesKey }),
  });
}
