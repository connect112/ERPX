import { apiClient } from "@/api/client";
import type { DepreciationMethod } from "@/features/assets/categories/schemas/asset-category-schemas";

export interface AssetCategoryPublic {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  default_useful_life_years: number;
  default_depreciation_method: DepreciationMethod;
  is_active: boolean;
  created_at: string;
}

export interface AssetCategoryCreatePayload {
  name: string;
  code: string;
  default_useful_life_years: number;
  default_depreciation_method?: DepreciationMethod;
}

export interface AssetCategoryUpdatePayload {
  name?: string;
  default_useful_life_years?: number;
  default_depreciation_method?: DepreciationMethod;
  is_active?: boolean;
}

export const assetCategoriesApi = {
  list: (isActive?: boolean) =>
    apiClient
      .get<AssetCategoryPublic[]>("/assets/categories", { params: { is_active: isActive } })
      .then((r) => r.data),

  create: (payload: AssetCategoryCreatePayload) =>
    apiClient.post<AssetCategoryPublic>("/assets/categories", payload).then((r) => r.data),

  update: (id: string, payload: AssetCategoryUpdatePayload) =>
    apiClient.patch<AssetCategoryPublic>(`/assets/categories/${id}`, payload).then((r) => r.data),
};
