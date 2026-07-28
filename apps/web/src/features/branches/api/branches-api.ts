import { apiClient } from "@/api/client";

export interface BranchPublic {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  phone: string | null;
  email: string | null;
  is_head_office: boolean;
  is_active: boolean;
  created_at: string;
}

export interface BranchCreatePayload {
  organization_id: string;
  name: string;
  code: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  phone?: string;
  email?: string;
  is_head_office?: boolean;
}

export interface BranchUpdatePayload {
  name?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  phone?: string;
  email?: string;
  is_head_office?: boolean;
  is_active?: boolean;
}

export const branchesApi = {
  list: (organizationId: string) =>
    apiClient
      .get<BranchPublic[]>("/branches", { params: { organization_id: organizationId } })
      .then((r) => r.data),

  create: (payload: BranchCreatePayload) =>
    apiClient.post<BranchPublic>("/branches", payload).then((r) => r.data),

  update: (id: string, payload: BranchUpdatePayload) =>
    apiClient.patch<BranchPublic>(`/branches/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/branches/${id}`).then((r) => r.data),
};
