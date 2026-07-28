import { apiClient } from "@/api/client";
import type { InvoiceStatus } from "@/features/accounting/invoices/schemas/invoice-schemas";

export interface InvoiceLinePublic {
  id: string;
  revenue_account_id: string;
  gst_rate_id: string | null;
  description: string;
  quantity: number;
  unit_price: number;
  line_subtotal: number;
  tax_amount: number;
  line_total: number;
}

export interface InvoicePublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  customer_id: string;
  receivable_account_id: string;
  tax_payable_account_id: string | null;
  discount_account_id: string | null;
  journal_entry_id: string | null;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  is_interstate: boolean;
  subtotal_amount: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  amount_paid: number;
  status: InvoiceStatus;
  notes: string | null;
  created_at: string;
  lines: InvoiceLinePublic[];
}

export interface InvoiceListResponse {
  items: InvoicePublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface InvoiceListParams {
  customer_id?: string;
  status?: InvoiceStatus;
  skip?: number;
  limit?: number;
}

export interface InvoiceLinePayload {
  revenue_account_id: string;
  description: string;
  quantity?: number;
  unit_price: number;
  gst_rate_id?: string;
}

export interface InvoiceCreatePayload {
  customer_id: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  receivable_account_id: string;
  tax_payable_account_id?: string;
  discount_account_id?: string;
  branch_id?: string;
  is_interstate?: boolean;
  discount_amount?: number;
  notes?: string;
  lines: InvoiceLinePayload[];
}

export const invoicesApi = {
  list: (params: InvoiceListParams) =>
    apiClient.get<InvoiceListResponse>("/accounting/invoices", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<InvoicePublic>(`/accounting/invoices/${id}`).then((r) => r.data),

  create: (payload: InvoiceCreatePayload) =>
    apiClient.post<InvoicePublic>("/accounting/invoices", payload).then((r) => r.data),

  post: (id: string) =>
    apiClient.post<InvoicePublic>(`/accounting/invoices/${id}/post`).then((r) => r.data),

  cancel: (id: string) =>
    apiClient.post<InvoicePublic>(`/accounting/invoices/${id}/cancel`).then((r) => r.data),
};
