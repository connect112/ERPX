import { apiClient } from "@/api/client";

export interface ItemCategoryPublic {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ItemCategoryCreatePayload {
  name: string;
  code: string;
  description?: string;
}

export interface ItemCategoryUpdatePayload {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export const itemCategoriesApi = {
  list: (isActive?: boolean) =>
    apiClient
      .get<ItemCategoryPublic[]>("/inventory/categories", { params: { is_active: isActive } })
      .then((r) => r.data),

  create: (payload: ItemCategoryCreatePayload) =>
    apiClient.post<ItemCategoryPublic>("/inventory/categories", payload).then((r) => r.data),

  update: (id: string, payload: ItemCategoryUpdatePayload) =>
    apiClient.patch<ItemCategoryPublic>(`/inventory/categories/${id}`, payload).then((r) => r.data),
};
