import { apiClient } from "@/api/client";

export interface CategoryPublic {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CategoryCreatePayload {
  name: string;
  slug: string;
  description?: string;
}

export interface CategoryUpdatePayload {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export const categoriesApi = {
  list: () => apiClient.get<CategoryPublic[]>("/courses/categories").then((r) => r.data),

  create: (payload: CategoryCreatePayload) =>
    apiClient.post<CategoryPublic>("/courses/categories", payload).then((r) => r.data),

  update: (id: string, payload: CategoryUpdatePayload) =>
    apiClient.patch<CategoryPublic>(`/courses/categories/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/courses/categories/${id}`).then((r) => r.data),
};
