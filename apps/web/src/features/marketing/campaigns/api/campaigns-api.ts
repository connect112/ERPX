import { apiClient } from "@/api/client";
import type { CampaignChannel, CampaignStatus } from "@/features/marketing/campaigns/schemas/campaign-schemas";

export interface CampaignPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  created_by_user_id: string | null;
  campaign_code: string;
  name: string;
  channel: CampaignChannel;
  status: CampaignStatus;
  start_date: string;
  end_date: string | null;
  budget_amount: number | null;
  actual_spend: number;
  target_audience: string | null;
  goal: string | null;
  notes: string | null;
  created_at: string;
}

export interface CampaignListResponse {
  items: CampaignPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface CampaignListParams {
  channel?: CampaignChannel;
  status?: CampaignStatus;
  skip?: number;
  limit?: number;
}

export interface CampaignCreatePayload {
  campaign_code: string;
  name: string;
  branch_id?: string;
  channel: CampaignChannel;
  start_date: string;
  end_date?: string;
  budget_amount?: number;
  target_audience?: string;
  goal?: string;
  notes?: string;
}

export interface CampaignUpdatePayload {
  name?: string;
  end_date?: string;
  budget_amount?: number;
  actual_spend?: number;
  target_audience?: string;
  goal?: string;
  notes?: string;
}

export interface CampaignPerformance {
  campaign_id: string;
  leads_generated: number;
  leads_converted: number;
  conversion_rate_percent: number;
  landing_pages_count: number;
  landing_page_views: number;
  coupons_count: number;
  coupon_redemptions: number;
  coupon_discount_given: number;
  budget_amount: number | null;
  actual_spend: number;
  cost_per_lead: number | null;
}

export const campaignsApi = {
  list: (params: CampaignListParams) =>
    apiClient.get<CampaignListResponse>("/marketing/campaigns", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<CampaignPublic>(`/marketing/campaigns/${id}`).then((r) => r.data),

  create: (payload: CampaignCreatePayload) =>
    apiClient.post<CampaignPublic>("/marketing/campaigns", payload).then((r) => r.data),

  update: (id: string, payload: CampaignUpdatePayload) =>
    apiClient.patch<CampaignPublic>(`/marketing/campaigns/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, status: CampaignStatus) =>
    apiClient.post<CampaignPublic>(`/marketing/campaigns/${id}/status`, { status }).then((r) => r.data),

  performance: (id: string) =>
    apiClient
      .get<CampaignPerformance>(`/marketing/analytics/campaigns/${id}/performance`)
      .then((r) => r.data),
};
