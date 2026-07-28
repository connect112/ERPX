import { apiClient } from "@/api/client";

export interface MarketingOverview {
  total_campaigns: number;
  active_campaigns: number;
  total_leads_from_campaigns: number;
  total_landing_page_views: number;
  total_coupon_redemptions: number;
  total_coupon_discount_given: number;
  total_referrals: number;
  referrals_converted: number;
  referrals_rewarded: number;
}

export const marketingAnalyticsApi = {
  overview: () => apiClient.get<MarketingOverview>("/marketing/analytics/overview").then((r) => r.data),
};
