import { apiClient } from "@/api/client";

export interface VendorPublic {
  id: string;
  organization_id: string;
  vendor_code: string;
  name: string;
  email: string | null;
  phone: string | null;
  gstin: string | null;
  pan_number: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  bank_account_number: string | null;
  bank_ifsc_code: string | null;
  bank_name: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
}

export interface VendorListResponse {
  items: VendorPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface VendorListParams {
  is_active?: boolean;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface VendorCreatePayload {
  vendor_code: string;
  name: string;
  email?: string;
  phone?: string;
  gstin?: string;
  pan_number?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  bank_account_number?: string;
  bank_ifsc_code?: string;
  bank_name?: string;
  notes?: string;
}

export type VendorUpdatePayload = Partial<Omit<VendorCreatePayload, "vendor_code">> & {
  is_active?: boolean;
};

export const vendorsApi = {
  list: (params: VendorListParams) =>
    apiClient.get<VendorListResponse>("/accounting/vendors", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<VendorPublic>(`/accounting/vendors/${id}`).then((r) => r.data),

  create: (payload: VendorCreatePayload) =>
    apiClient.post<VendorPublic>("/accounting/vendors", payload).then((r) => r.data),

  update: (id: string, payload: VendorUpdatePayload) =>
    apiClient.patch<VendorPublic>(`/accounting/vendors/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/accounting/vendors/${id}`).then((r) => r.data),
};
