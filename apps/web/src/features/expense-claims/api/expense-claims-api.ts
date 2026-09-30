import { apiClient } from "@/api/client";

export type ExpenseClaimStatus = "pending" | "approved" | "rejected";

export interface ExpenseClaim {
  id: string;
  organization_id: string;
  employee_id: string;
  receipt_document_id: string | null;
  reviewed_by_user_id: string | null;
  period_year: number;
  period_month: number;
  applied_payroll_run_id: string | null;
  description: string;
  amount: number;
  status: ExpenseClaimStatus;
  rejection_reason: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface ExpenseClaimListResponse {
  items: ExpenseClaim[];
  total: number;
  skip: number;
  limit: number;
}

export interface ExpenseClaimListParams {
  status?: ExpenseClaimStatus;
  skip?: number;
  limit?: number;
}

export const expenseClaimsApi = {
  list: (params: ExpenseClaimListParams) =>
    apiClient.get<ExpenseClaimListResponse>("/expense-claims", { params }).then((r) => r.data),

  approve: (id: string) =>
    apiClient.post<ExpenseClaim>(`/expense-claims/${id}/approve`).then((r) => r.data),

  reject: (id: string, rejectionReason: string) =>
    apiClient
      .post<ExpenseClaim>(`/expense-claims/${id}/reject`, { rejection_reason: rejectionReason })
      .then((r) => r.data),
};
