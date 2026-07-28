import { apiClient } from "@/api/client";

export interface GSTRatePublic {
  id: string;
  organization_id: string;
  name: string;
  rate_percent: number;
  hsn_sac_code: string | null;
  is_active: boolean;
  created_at: string;
}

export interface GSTRateCreatePayload {
  name: string;
  rate_percent: number;
  hsn_sac_code?: string;
}

export interface GSTRateUpdatePayload {
  name?: string;
  rate_percent?: number;
  hsn_sac_code?: string;
  is_active?: boolean;
}

export interface TaxComputationResponse {
  taxable_amount: number;
  rate_percent: number;
  is_interstate: boolean;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  total_tax: number;
  total_amount: number;
}

export interface GSTReturnSummaryResponse {
  period_from: string;
  period_to: string;
  output_taxable_value: number;
  output_tax_collected: number;
  input_taxable_value: number;
  input_tax_credit: number;
  net_tax_payable: number;
}

export const gstApi = {
  listRates: (isActive?: boolean) =>
    apiClient
      .get<GSTRatePublic[]>("/accounting/gst/rates", { params: { is_active: isActive } })
      .then((r) => r.data),

  createRate: (payload: GSTRateCreatePayload) =>
    apiClient.post<GSTRatePublic>("/accounting/gst/rates", payload).then((r) => r.data),

  updateRate: (id: string, payload: GSTRateUpdatePayload) =>
    apiClient.patch<GSTRatePublic>(`/accounting/gst/rates/${id}`, payload).then((r) => r.data),

  computeTax: (taxableAmount: number, gstRateId: string, isInterstate: boolean) =>
    apiClient
      .post<TaxComputationResponse>("/accounting/gst/compute", {
        taxable_amount: taxableAmount,
        gst_rate_id: gstRateId,
        is_interstate: isInterstate,
      })
      .then((r) => r.data),

  getReturnSummary: (periodFrom: string, periodTo: string) =>
    apiClient
      .get<GSTReturnSummaryResponse>("/accounting/gst/returns/summary", {
        params: { period_from: periodFrom, period_to: periodTo },
      })
      .then((r) => r.data),
};
