import { apiClient } from "@/api/client";
import type { QuotationStatus } from "@/features/corporate/quotations/schemas/quotation-schemas";

export interface QuotationLinePublic {
  id: string;
  gst_rate_id: string | null;
  description: string;
  quantity: number;
  unit_price: number;
  line_subtotal: number;
  tax_amount: number;
  line_total: number;
}

export interface QuotationPublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_id: string | null;
  quotation_number: string;
  quotation_date: string;
  valid_until: string;
  status: QuotationStatus;
  subtotal_amount: number;
  tax_amount: number;
  total_amount: number;
  notes: string | null;
  rejection_reason: string | null;
  created_at: string;
  lines: QuotationLinePublic[];
}

export interface QuotationListResponse {
  items: QuotationPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface QuotationListParams {
  client_id?: string;
  status?: QuotationStatus;
  skip?: number;
  limit?: number;
}

export interface QuotationLinePayload {
  description: string;
  quantity: number;
  unit_price: number;
  gst_rate_id?: string;
}

export interface QuotationCreatePayload {
  client_id: string;
  project_id?: string;
  quotation_number: string;
  quotation_date: string;
  valid_until: string;
  notes?: string;
  lines: QuotationLinePayload[];
}

export interface QuotationUpdatePayload {
  valid_until?: string;
  notes?: string;
  lines?: QuotationLinePayload[];
}

export const quotationsApi = {
  list: (params: QuotationListParams) =>
    apiClient.get<QuotationListResponse>("/corporate/quotations", { params }).then((r) => r.data),

  get: (id: string) =>
    apiClient.get<QuotationPublic>(`/corporate/quotations/${id}`).then((r) => r.data),

  create: (payload: QuotationCreatePayload) =>
    apiClient.post<QuotationPublic>("/corporate/quotations", payload).then((r) => r.data),

  update: (id: string, payload: QuotationUpdatePayload) =>
    apiClient.patch<QuotationPublic>(`/corporate/quotations/${id}`, payload).then((r) => r.data),

  send: (id: string) =>
    apiClient.post<QuotationPublic>(`/corporate/quotations/${id}/send`).then((r) => r.data),

  accept: (id: string) =>
    apiClient.post<QuotationPublic>(`/corporate/quotations/${id}/accept`).then((r) => r.data),

  reject: (id: string, rejectionReason?: string) =>
    apiClient
      .post<QuotationPublic>(`/corporate/quotations/${id}/reject`, { rejection_reason: rejectionReason })
      .then((r) => r.data),
};
