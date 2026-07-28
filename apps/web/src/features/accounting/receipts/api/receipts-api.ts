import { apiClient } from "@/api/client";
import type { PaymentMode, ReceiptStatus } from "@/features/accounting/receipts/schemas/receipt-schemas";

export interface ReceiptPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  customer_id: string;
  invoice_id: string | null;
  deposit_account_id: string;
  bank_account_id: string | null;
  journal_entry_id: string | null;
  receipt_number: string;
  receipt_date: string;
  amount: number;
  payment_mode: PaymentMode;
  reference_number: string | null;
  status: ReceiptStatus;
  notes: string | null;
  created_at: string;
}

export interface ReceiptListResponse {
  items: ReceiptPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ReceiptListParams {
  customer_id?: string;
  invoice_id?: string;
  status?: ReceiptStatus;
  skip?: number;
  limit?: number;
}

export interface ReceiptCreatePayload {
  customer_id: string;
  invoice_id?: string;
  receivable_account_id?: string;
  receipt_number: string;
  receipt_date: string;
  amount: number;
  payment_mode: PaymentMode;
  bank_account_id?: string;
  deposit_account_id?: string;
  branch_id?: string;
  reference_number?: string;
  notes?: string;
}

export const receiptsApi = {
  list: (params: ReceiptListParams) =>
    apiClient.get<ReceiptListResponse>("/accounting/receipts", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<ReceiptPublic>(`/accounting/receipts/${id}`).then((r) => r.data),

  create: (payload: ReceiptCreatePayload) =>
    apiClient.post<ReceiptPublic>("/accounting/receipts", payload).then((r) => r.data),

  void: (id: string) =>
    apiClient.post<ReceiptPublic>(`/accounting/receipts/${id}/void`).then((r) => r.data),
};
