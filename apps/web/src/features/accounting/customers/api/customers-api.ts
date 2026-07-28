import { apiClient } from "@/api/client";
import type { CustomerType } from "@/features/accounting/customers/schemas/customer-schemas";

export interface CustomerPublic {
  id: string;
  organization_id: string;
  student_id: string | null;
  customer_code: string;
  name: string;
  customer_type: CustomerType;
  email: string | null;
  phone: string | null;
  gstin: string | null;
  billing_address_line1: string | null;
  billing_address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  credit_limit: number;
  notes: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CustomerListResponse {
  items: CustomerPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface CustomerListParams {
  is_active?: boolean;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface CustomerCreatePayload {
  customer_code: string;
  name: string;
  customer_type: CustomerType;
  student_id?: string;
  email?: string;
  phone?: string;
  gstin?: string;
  billing_address_line1?: string;
  billing_address_line2?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  credit_limit?: number;
  notes?: string;
}

export type CustomerUpdatePayload = Partial<
  Omit<CustomerCreatePayload, "customer_code" | "customer_type" | "student_id">
> & { is_active?: boolean };

export const customersApi = {
  list: (params: CustomerListParams) =>
    apiClient.get<CustomerListResponse>("/accounting/customers", { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<CustomerPublic>(`/accounting/customers/${id}`).then((r) => r.data),

  create: (payload: CustomerCreatePayload) =>
    apiClient.post<CustomerPublic>("/accounting/customers", payload).then((r) => r.data),

  update: (id: string, payload: CustomerUpdatePayload) =>
    apiClient.patch<CustomerPublic>(`/accounting/customers/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/accounting/customers/${id}`).then((r) => r.data),
};
