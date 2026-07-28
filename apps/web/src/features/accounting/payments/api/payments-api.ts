import { apiClient } from "@/api/client";
import type {
  ApPaymentMode,
  PaymentStatus,
} from "@/features/accounting/payments/schemas/payment-schemas";

export interface PaymentPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  vendor_id: string;
  expense_id: string;
  payment_account_id: string;
  bank_account_id: string | null;
  tds_payable_account_id: string | null;
  tds_section_id: string | null;
  tds_deduction_id: string | null;
  journal_entry_id: string | null;
  payment_number: string;
  payment_date: string;
  gross_amount: number;
  tds_amount: number;
  net_amount: number;
  payment_mode: ApPaymentMode;
  reference_number: string | null;
  status: PaymentStatus;
  notes: string | null;
  created_at: string;
}

export interface PaymentListResponse {
  items: PaymentPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface PaymentListParams {
  vendor_id?: string;
  expense_id?: string;
  status?: PaymentStatus;
  skip?: number;
  limit?: number;
}

export interface PaymentCreatePayload {
  vendor_id: string;
  expense_id: string;
  payment_number: string;
  payment_date: string;
  gross_amount: number;
  payment_mode: ApPaymentMode;
  bank_account_id?: string;
  payment_account_id?: string;
  tds_section_id?: string;
  tds_payable_account_id?: string;
  branch_id?: string;
  reference_number?: string;
  notes?: string;
}

export const paymentsApi = {
  list: (params: PaymentListParams) =>
    apiClient.get<PaymentListResponse>("/accounting/payments", { params }).then((r) => r.data),

  create: (payload: PaymentCreatePayload) =>
    apiClient.post<PaymentPublic>("/accounting/payments", payload).then((r) => r.data),

  void: (id: string) =>
    apiClient.post<PaymentPublic>(`/accounting/payments/${id}/void`).then((r) => r.data),
};
