import { apiClient } from "@/api/client";

export interface TDSSectionPublic {
  id: string;
  organization_id: string;
  section_code: string;
  description: string;
  rate_percent: number;
  threshold_amount: number;
  is_active: boolean;
  created_at: string;
}

export interface TDSDeductionPublic {
  id: string;
  organization_id: string;
  vendor_id: string;
  tds_section_id: string;
  payment_id: string | null;
  gross_amount: number;
  tds_amount: number;
  net_amount: number;
  financial_year: string;
  certificate_number: string | null;
  deduction_date: string;
  created_at: string;
}

export interface TDSSectionCreatePayload {
  section_code: string;
  description: string;
  rate_percent: number;
  threshold_amount?: number;
}

export interface TDSSectionUpdatePayload {
  description?: string;
  rate_percent?: number;
  threshold_amount?: number;
  is_active?: boolean;
}

export const tdsApi = {
  listSections: (isActive?: boolean) =>
    apiClient
      .get<TDSSectionPublic[]>("/accounting/tds/sections", { params: { is_active: isActive } })
      .then((r) => r.data),

  createSection: (payload: TDSSectionCreatePayload) =>
    apiClient.post<TDSSectionPublic>("/accounting/tds/sections", payload).then((r) => r.data),

  updateSection: (id: string, payload: TDSSectionUpdatePayload) =>
    apiClient.patch<TDSSectionPublic>(`/accounting/tds/sections/${id}`, payload).then((r) => r.data),

  listDeductionsForVendor: (vendorId: string, financialYear?: string) =>
    apiClient
      .get<TDSDeductionPublic[]>(`/accounting/tds/deductions/by-vendor/${vendorId}`, {
        params: { financial_year: financialYear },
      })
      .then((r) => r.data),
};
