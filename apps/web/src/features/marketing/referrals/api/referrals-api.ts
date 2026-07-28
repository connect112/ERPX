import { apiClient } from "@/api/client";
import type { ReferralStatus } from "@/features/marketing/referrals/schemas/referral-schemas";

export interface ReferralProgramPublic {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  referrer_reward_amount: number;
  referee_discount_amount: number;
  max_referrals_per_referrer: number | null;
  valid_from: string;
  valid_until: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ReferralProgramCreatePayload {
  name: string;
  code: string;
  referrer_reward_amount: number;
  referee_discount_amount?: number;
  max_referrals_per_referrer?: number;
  valid_from: string;
  valid_until?: string;
}

export interface ReferralProgramUpdatePayload {
  referrer_reward_amount?: number;
  referee_discount_amount?: number;
  max_referrals_per_referrer?: number;
  valid_until?: string;
  is_active?: boolean;
}

export interface ReferralPublic {
  id: string;
  organization_id: string;
  referral_program_id: string;
  referrer_student_id: string | null;
  converted_lead_id: string | null;
  referee_name: string;
  referee_email: string | null;
  referee_phone: string | null;
  status: ReferralStatus;
  reward_amount: number | null;
  rewarded_at: string | null;
  created_at: string;
}

export interface ReferralListResponse {
  items: ReferralPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ReferralListParams {
  referral_program_id?: string;
  status?: ReferralStatus;
  skip?: number;
  limit?: number;
}

export interface ReferralCreatePayload {
  referral_program_id: string;
  referrer_student_id?: string;
  referee_name: string;
  referee_email?: string;
  referee_phone?: string;
}

export const referralsApi = {
  listPrograms: (isActive?: boolean) =>
    apiClient
      .get<ReferralProgramPublic[]>("/marketing/referrals/programs", { params: { is_active: isActive } })
      .then((r) => r.data),

  createProgram: (payload: ReferralProgramCreatePayload) =>
    apiClient.post<ReferralProgramPublic>("/marketing/referrals/programs", payload).then((r) => r.data),

  updateProgram: (id: string, payload: ReferralProgramUpdatePayload) =>
    apiClient.patch<ReferralProgramPublic>(`/marketing/referrals/programs/${id}`, payload).then((r) => r.data),

  list: (params: ReferralListParams) =>
    apiClient.get<ReferralListResponse>("/marketing/referrals", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<ReferralPublic>(`/marketing/referrals/${id}`).then((r) => r.data),

  create: (payload: ReferralCreatePayload) =>
    apiClient.post<ReferralPublic>("/marketing/referrals", payload).then((r) => r.data),

  convert: (id: string, convertedLeadId: string) =>
    apiClient
      .post<ReferralPublic>(`/marketing/referrals/${id}/convert`, { converted_lead_id: convertedLeadId })
      .then((r) => r.data),

  reward: (id: string) =>
    apiClient.post<ReferralPublic>(`/marketing/referrals/${id}/reward`).then((r) => r.data),

  reject: (id: string) =>
    apiClient.post<ReferralPublic>(`/marketing/referrals/${id}/reject`).then((r) => r.data),
};
