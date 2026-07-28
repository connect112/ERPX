import { apiClient } from "@/api/client";
import type { SubscriptionPlan } from "@/features/organizations/schemas/organization-schemas";

export interface OrganizationPublic {
  id: string;
  name: string;
  slug: string;
  legal_name: string | null;
  industry: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  logo_url: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  subscription_plan: SubscriptionPlan;
  is_active: boolean;
  created_at: string;
}

export interface OrganizationListParams {
  skip?: number;
  limit?: number;
}

export interface OrganizationCreatePayload {
  name: string;
  slug: string;
  legal_name?: string;
  industry?: string;
  email?: string;
  phone?: string;
  website?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  subscription_plan?: SubscriptionPlan;
}

export interface OrganizationUpdatePayload {
  name?: string;
  legal_name?: string;
  industry?: string;
  email?: string;
  phone?: string;
  website?: string;
  logo_url?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  subscription_plan?: SubscriptionPlan;
  is_active?: boolean;
}

export const organizationsApi = {
  list: (params: OrganizationListParams) =>
    apiClient.get<OrganizationPublic[]>("/organizations", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<OrganizationPublic>(`/organizations/${id}`).then((r) => r.data),

  create: (payload: OrganizationCreatePayload) =>
    apiClient.post<OrganizationPublic>("/organizations", payload).then((r) => r.data),

  update: (id: string, payload: OrganizationUpdatePayload) =>
    apiClient.patch<OrganizationPublic>(`/organizations/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/organizations/${id}`).then((r) => r.data),
};
