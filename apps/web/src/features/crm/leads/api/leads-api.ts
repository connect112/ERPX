import { apiClient } from "@/api/client";
import type { LeadSource, LeadStatus } from "@/features/crm/leads/schemas/lead-schemas";

export interface LeadPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  campaign_id: string | null;
  full_name: string;
  email: string | null;
  phone: string | null;
  source: LeadSource;
  status: LeadStatus;
  assigned_to_user_id: string | null;
  notes: string | null;
  lost_reason: string | null;
  created_at: string;
}

export interface LeadListResponse {
  items: LeadPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface LeadListParams {
  status?: LeadStatus;
  assigned_to_user_id?: string;
  campaign_id?: string;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface LeadCreatePayload {
  full_name: string;
  email?: string;
  phone?: string;
  branch_id?: string;
  campaign_id?: string;
  source: LeadSource;
  assigned_to_user_id?: string;
  notes?: string;
}

export type LeadUpdatePayload = Partial<LeadCreatePayload>;

export interface LeadStatusChangePayload {
  status: LeadStatus;
  lost_reason?: string;
}

export const leadsApi = {
  list: (params: LeadListParams) =>
    apiClient.get<LeadListResponse>("/crm/leads", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<LeadPublic>(`/crm/leads/${id}`).then((r) => r.data),

  create: (payload: LeadCreatePayload) =>
    apiClient.post<LeadPublic>("/crm/leads", payload).then((r) => r.data),

  update: (id: string, payload: LeadUpdatePayload) =>
    apiClient.patch<LeadPublic>(`/crm/leads/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, payload: LeadStatusChangePayload) =>
    apiClient.post<LeadPublic>(`/crm/leads/${id}/status`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/crm/leads/${id}`).then((r) => r.data),
};
