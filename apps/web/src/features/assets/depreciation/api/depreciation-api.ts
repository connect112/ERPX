import { apiClient } from "@/api/client";
import type { DepreciationRunStatus } from "@/features/assets/depreciation/schemas/depreciation-schemas";

export interface DepreciationRunPublic {
  id: string;
  organization_id: string;
  journal_entry_id: string | null;
  period_year: number;
  period_month: number;
  run_date: string;
  status: DepreciationRunStatus;
  total_depreciation_amount: number;
  posted_at: string | null;
  created_at: string;
}

export interface DepreciationRunListResponse {
  items: DepreciationRunPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface DepreciationRunListParams {
  skip?: number;
  limit?: number;
}

export interface DepreciationRunGeneratePayload {
  period_year: number;
  period_month: number;
  run_date: string;
}

export interface DepreciationEntryPublic {
  id: string;
  depreciation_run_id: string;
  asset_id: string;
  depreciation_amount: number;
  accumulated_depreciation: number;
  net_book_value: number;
  created_at: string;
}

export interface DepreciationRunGenerationResult {
  run: DepreciationRunPublic;
  assets_processed: number;
  assets_fully_depreciated_skipped: string[];
}

export const depreciationApi = {
  generate: (payload: DepreciationRunGeneratePayload) =>
    apiClient.post<DepreciationRunGenerationResult>("/assets/depreciation-runs", payload).then((r) => r.data),

  list: (params: DepreciationRunListParams) =>
    apiClient
      .get<DepreciationRunListResponse>("/assets/depreciation-runs", { params })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient.get<DepreciationRunPublic>(`/assets/depreciation-runs/${id}`).then((r) => r.data),

  listEntries: (runId: string) =>
    apiClient
      .get<DepreciationEntryPublic[]>(`/assets/depreciation-runs/${runId}/entries`)
      .then((r) => r.data),

  post: (id: string) =>
    apiClient.post<DepreciationRunPublic>(`/assets/depreciation-runs/${id}/post`).then((r) => r.data),

  cancel: (id: string) =>
    apiClient.post<DepreciationRunPublic>(`/assets/depreciation-runs/${id}/cancel`).then((r) => r.data),
};
