import { apiClient } from "@/api/client";
import type { CouponDiscountType } from "@/features/marketing/coupons/schemas/coupon-schemas";

export interface CouponPublic {
  id: string;
  organization_id: string;
  campaign_id: string | null;
  code: string;
  description: string | null;
  discount_type: CouponDiscountType;
  discount_value: number;
  max_discount_amount: number | null;
  min_order_amount: number;
  usage_limit_total: number | null;
  usage_limit_per_customer: number;
  valid_from: string;
  valid_until: string;
  is_active: boolean;
  created_at: string;
}

export interface CouponListResponse {
  items: CouponPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface CouponListParams {
  campaign_id?: string;
  is_active?: boolean;
  skip?: number;
  limit?: number;
}

export interface CouponCreatePayload {
  code: string;
  campaign_id?: string;
  description?: string;
  discount_type: CouponDiscountType;
  discount_value: number;
  max_discount_amount?: number;
  min_order_amount?: number;
  usage_limit_total?: number;
  usage_limit_per_customer?: number;
  valid_from: string;
  valid_until: string;
}

export interface CouponUpdatePayload {
  description?: string;
  max_discount_amount?: number;
  min_order_amount?: number;
  usage_limit_total?: number;
  usage_limit_per_customer?: number;
  valid_until?: string;
  is_active?: boolean;
}

export interface CouponRedemptionPublic {
  id: string;
  coupon_id: string;
  redeemed_by_reference: string;
  redeemed_against_type: string | null;
  redeemed_against_id: string | null;
  order_amount: number;
  discount_amount_applied: number;
  redeemed_at: string;
}

export interface CouponRedemptionListResponse {
  items: CouponRedemptionPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface CouponUsageSummary {
  coupon_id: string;
  redemption_count: number;
  total_discount_given: number;
}

export const couponsApi = {
  list: (params: CouponListParams) =>
    apiClient.get<CouponListResponse>("/marketing/coupons", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<CouponPublic>(`/marketing/coupons/${id}`).then((r) => r.data),

  create: (payload: CouponCreatePayload) =>
    apiClient.post<CouponPublic>("/marketing/coupons", payload).then((r) => r.data),

  update: (id: string, payload: CouponUpdatePayload) =>
    apiClient.patch<CouponPublic>(`/marketing/coupons/${id}`, payload).then((r) => r.data),

  usageSummary: (id: string) =>
    apiClient.get<CouponUsageSummary>(`/marketing/coupons/${id}/usage-summary`).then((r) => r.data),

  listRedemptions: (id: string, params: { skip?: number; limit?: number }) =>
    apiClient
      .get<CouponRedemptionListResponse>(`/marketing/coupons/${id}/redemptions`, { params })
      .then((r) => r.data),
};
