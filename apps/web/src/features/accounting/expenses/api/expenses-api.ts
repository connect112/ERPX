import { apiClient } from "@/api/client";
import type { ExpenseStatus } from "@/features/accounting/expenses/schemas/expense-schemas";

export interface ExpensePublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  vendor_id: string;
  expense_account_id: string;
  payable_account_id: string;
  input_tax_credit_account_id: string | null;
  gst_rate_id: string | null;
  journal_entry_id: string | null;
  approved_by_user_id: string | null;
  expense_number: string;
  expense_date: string;
  category: string;
  description: string;
  is_interstate: boolean;
  subtotal_amount: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  status: ExpenseStatus;
  attachment_url: string | null;
  rejection_reason: string | null;
  notes: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface ExpenseListResponse {
  items: ExpensePublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ExpenseListParams {
  vendor_id?: string;
  status?: ExpenseStatus;
  category?: string;
  skip?: number;
  limit?: number;
}

export interface ExpenseCreatePayload {
  vendor_id: string;
  expense_account_id: string;
  payable_account_id: string;
  expense_number: string;
  expense_date: string;
  category: string;
  description: string;
  subtotal_amount: number;
  gst_rate_id?: string;
  input_tax_credit_account_id?: string;
  is_interstate?: boolean;
  attachment_url?: string;
  notes?: string;
}

export const expensesApi = {
  list: (params: ExpenseListParams) =>
    apiClient.get<ExpenseListResponse>("/accounting/expenses", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<ExpensePublic>(`/accounting/expenses/${id}`).then((r) => r.data),

  create: (payload: ExpenseCreatePayload) =>
    apiClient.post<ExpensePublic>("/accounting/expenses", payload).then((r) => r.data),

  approve: (id: string) =>
    apiClient.post<ExpensePublic>(`/accounting/expenses/${id}/approve`).then((r) => r.data),

  reject: (id: string, rejectionReason: string) =>
    apiClient
      .post<ExpensePublic>(`/accounting/expenses/${id}/reject`, { rejection_reason: rejectionReason })
      .then((r) => r.data),

  cancel: (id: string) =>
    apiClient.post<ExpensePublic>(`/accounting/expenses/${id}/cancel`).then((r) => r.data),
};
