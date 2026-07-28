import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type CategoryCreatePayload,
  type CategoryUpdatePayload,
  categoriesApi,
} from "@/features/courses/categories/api/categories-api";

const categoriesKey = ["courses", "categories"] as const;

export function useCategories() {
  return useQuery({
    queryKey: categoriesKey,
    queryFn: categoriesApi.list,
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CategoryCreatePayload) => categoriesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoriesKey }),
  });
}

export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: CategoryUpdatePayload }) =>
      categoriesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoriesKey }),
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => categoriesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoriesKey }),
  });
}
