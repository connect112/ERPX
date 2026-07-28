import { apiClient } from "@/api/client";
import type { ClientStatus } from "@/features/corporate/clients/schemas/client-schemas";

export interface ClientPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  accounting_customer_id: string | null;
  account_manager_user_id: string | null;
  client_code: string;
  name: string;
  industry: string | null;
  website: string | null;
  gstin: string | null;
  contact_person_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  status: ClientStatus;
  notes: string | null;
  created_at: string;
}

export interface ClientListResponse {
  items: ClientPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ClientListParams {
  status?: ClientStatus;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface ClientCreatePayload {
  client_code: string;
  name: string;
  branch_id?: string;
  accounting_customer_id?: string;
  account_manager_user_id?: string;
  industry?: string;
  website?: string;
  gstin?: string;
  contact_person_name?: string;
  contact_email?: string;
  contact_phone?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  notes?: string;
}

export type ClientUpdatePayload = Partial<Omit<ClientCreatePayload, "client_code">>;

export const clientsApi = {
  list: (params: ClientListParams) =>
    apiClient.get<ClientListResponse>("/corporate/clients", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<ClientPublic>(`/corporate/clients/${id}`).then((r) => r.data),

  create: (payload: ClientCreatePayload) =>
    apiClient.post<ClientPublic>("/corporate/clients", payload).then((r) => r.data),

  update: (id: string, payload: ClientUpdatePayload) =>
    apiClient.patch<ClientPublic>(`/corporate/clients/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, status: ClientStatus) =>
    apiClient.post<ClientPublic>(`/corporate/clients/${id}/status`, { status }).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/corporate/clients/${id}`).then((r) => r.data),
};
