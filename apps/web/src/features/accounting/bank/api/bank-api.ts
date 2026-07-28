import { apiClient } from "@/api/client";
import type {
  BankAccountType,
  BankTransactionSource,
} from "@/features/accounting/bank/schemas/bank-schemas";

export interface BankAccountPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  gl_account_id: string;
  account_name: string;
  account_type: BankAccountType;
  bank_name: string | null;
  account_number: string | null;
  ifsc_code: string | null;
  opening_balance: number;
  is_active: boolean;
  created_at: string;
}

export interface BankTransactionPublic {
  id: string;
  bank_account_id: string;
  journal_entry_id: string | null;
  transaction_date: string;
  description: string;
  debit_amount: number;
  credit_amount: number;
  reference_number: string | null;
  source: BankTransactionSource;
  source_id: string | null;
  is_reconciled: boolean;
  reconciled_at: string | null;
  created_at: string;
}

export interface BankTransactionListResponse {
  items: BankTransactionPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface BankAccountBalanceResponse {
  bank_account_id: string;
  account_name: string;
  as_of_date: string | null;
  opening_balance: number;
  total_debit: number;
  total_credit: number;
  closing_balance: number;
}

export interface BankAccountCreatePayload {
  gl_account_id: string;
  account_name: string;
  account_type: BankAccountType;
  bank_name?: string;
  account_number?: string;
  ifsc_code?: string;
  opening_balance?: number;
}

export interface BankAccountUpdatePayload {
  account_name?: string;
  bank_name?: string;
  account_number?: string;
  ifsc_code?: string;
  is_active?: boolean;
}

export interface BankTransactionCreatePayload {
  transaction_date: string;
  description: string;
  debit_amount?: number;
  credit_amount?: number;
  reference_number?: string;
  contra_account_id: string;
}

export const bankApi = {
  listAccounts: (isActive?: boolean) =>
    apiClient
      .get<BankAccountPublic[]>("/accounting/bank/accounts", { params: { is_active: isActive } })
      .then((r) => r.data),

  getAccount: (id: string) =>
    apiClient.get<BankAccountPublic>(`/accounting/bank/accounts/${id}`).then((r) => r.data),

  createAccount: (payload: BankAccountCreatePayload) =>
    apiClient.post<BankAccountPublic>("/accounting/bank/accounts", payload).then((r) => r.data),

  updateAccount: (id: string, payload: BankAccountUpdatePayload) =>
    apiClient.patch<BankAccountPublic>(`/accounting/bank/accounts/${id}`, payload).then((r) => r.data),

  getBalance: (id: string, asOfDate?: string) =>
    apiClient
      .get<BankAccountBalanceResponse>(`/accounting/bank/accounts/${id}/balance`, {
        params: { as_of_date: asOfDate },
      })
      .then((r) => r.data),

  createTransaction: (bankAccountId: string, payload: BankTransactionCreatePayload) =>
    apiClient
      .post<BankTransactionPublic>(`/accounting/bank/accounts/${bankAccountId}/transactions`, payload)
      .then((r) => r.data),

  listTransactions: (bankAccountId: string, isReconciled?: boolean) =>
    apiClient
      .get<BankTransactionListResponse>(`/accounting/bank/accounts/${bankAccountId}/transactions`, {
        params: { is_reconciled: isReconciled, limit: 100 },
      })
      .then((r) => r.data),

  reconcileTransaction: (transactionId: string) =>
    apiClient
      .post<BankTransactionPublic>(`/accounting/bank/transactions/${transactionId}/reconcile`)
      .then((r) => r.data),
};
