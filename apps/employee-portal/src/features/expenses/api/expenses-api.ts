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

export interface ReceiptUploadResponse {
  document_id: string;
  upload_url: string;
}

export const expensesApi = {
  requestReceiptUpload: (filename: string, contentType: string) =>
    apiClient
      .post<ReceiptUploadResponse>("/expense-claims/me/receipts/presigned-upload", {
        filename,
        content_type: contentType,
      })
      .then((r) => r.data),

  // Uploads directly to object storage using the presigned URL — deliberately
  // NOT `apiClient`, this must not go through the API's baseURL/auth
  // interceptors, it's a direct PUT to the storage endpoint.
  uploadToPresignedUrl: (uploadUrl: string, file: File) =>
    fetch(uploadUrl, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type || "application/octet-stream" },
    }),

  confirmReceiptUpload: (documentId: string) =>
    apiClient.post(`/expense-claims/me/receipts/${documentId}/confirm`).then((r) => r.data),

  submitClaim: (payload: { description: string; amount: number; receipt_document_id?: string }) =>
    apiClient.post<ExpenseClaim>("/expense-claims/me", payload).then((r) => r.data),

  myClaims: () => apiClient.get<ExpenseClaimListResponse>("/expense-claims/me").then((r) => r.data),
};
