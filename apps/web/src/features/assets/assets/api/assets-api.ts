import { apiClient } from "@/api/client";
import type { DepreciationMethod } from "@/features/assets/categories/schemas/asset-category-schemas";
import type { AssetStatus } from "@/features/assets/assets/schemas/asset-schemas";

export interface AssetPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  category_id: string | null;
  assigned_to_employee_id: string | null;
  asset_account_id: string;
  accumulated_depreciation_account_id: string;
  depreciation_expense_account_id: string;
  disposal_journal_entry_id: string | null;
  asset_code: string;
  name: string;
  description: string | null;
  location: string | null;
  purchase_date: string;
  purchase_cost: number;
  salvage_value: number;
  useful_life_years: number;
  depreciation_method: DepreciationMethod;
  status: AssetStatus;
  disposal_date: string | null;
  disposal_amount: number | null;
  notes: string | null;
  created_at: string;
}

export interface AssetListResponse {
  items: AssetPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface AssetListParams {
  category_id?: string;
  status?: AssetStatus;
  assigned_to_employee_id?: string;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface AssetCreatePayload {
  asset_code: string;
  name: string;
  category_id?: string;
  assigned_to_employee_id?: string;
  asset_account_id: string;
  accumulated_depreciation_account_id: string;
  depreciation_expense_account_id: string;
  description?: string;
  location?: string;
  purchase_date: string;
  purchase_cost: number;
  salvage_value?: number;
  useful_life_years: number;
  depreciation_method?: DepreciationMethod;
  notes?: string;
}

export interface AssetUpdatePayload {
  name?: string;
  category_id?: string;
  assigned_to_employee_id?: string;
  description?: string;
  location?: string;
  status?: AssetStatus;
  notes?: string;
}

export interface AssetNetBookValue {
  asset_id: string;
  as_of_date: string;
  purchase_cost: number;
  accumulated_depreciation: number;
  net_book_value: number;
}

export interface DisposeAssetPayload {
  disposal_date: string;
  disposal_amount: number;
  cash_account_id: string;
  gain_loss_account_id: string;
}

export const assetsApi = {
  list: (params: AssetListParams) =>
    apiClient.get<AssetListResponse>("/assets", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<AssetPublic>(`/assets/${id}`).then((r) => r.data),

  create: (payload: AssetCreatePayload) =>
    apiClient.post<AssetPublic>("/assets", payload).then((r) => r.data),

  update: (id: string, payload: AssetUpdatePayload) =>
    apiClient.patch<AssetPublic>(`/assets/${id}`, payload).then((r) => r.data),

  netBookValue: (id: string, asOfDate?: string) =>
    apiClient
      .get<AssetNetBookValue>(`/assets/${id}/net-book-value`, { params: { as_of_date: asOfDate } })
      .then((r) => r.data),

  dispose: (id: string, payload: DisposeAssetPayload) =>
    apiClient.post<AssetPublic>(`/assets/${id}/dispose`, payload).then((r) => r.data),
};
