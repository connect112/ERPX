import { apiClient } from "@/api/client";
import type { AccountType } from "@/features/accounting/ledger/schemas/account-schemas";

export interface AccountPublic {
  id: string;
  organization_id: string;
  parent_account_id: string | null;
  code: string;
  name: string;
  account_type: AccountType;
  account_subtype: string | null;
  description: string | null;
  opening_balance: number;
  is_system_account: boolean;
  is_active: boolean;
  created_at: string;
}

export interface AccountListResponse {
  items: AccountPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface AccountListParams {
  account_type?: AccountType;
  is_active?: boolean;
  search?: string;
  skip?: number;
  limit?: number;
}

export interface AccountBalanceResponse {
  account_id: string;
  code: string;
  name: string;
  account_type: AccountType;
  as_of_date: string | null;
  opening_balance: number;
  total_debit: number;
  total_credit: number;
  closing_balance: number;
}

export interface AccountCreatePayload {
  code: string;
  name: string;
  account_type: AccountType;
  account_subtype?: string;
  parent_account_id?: string;
  description?: string;
  opening_balance?: number;
}

export interface AccountUpdatePayload {
  name?: string;
  account_subtype?: string;
  parent_account_id?: string;
  description?: string;
  is_active?: boolean;
}

export const accountsApi = {
  list: (params: AccountListParams) =>
    apiClient.get<AccountListResponse>("/accounting/accounts", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<AccountPublic>(`/accounting/accounts/${id}`).then((r) => r.data),

  getBalance: (id: string, asOfDate?: string) =>
    apiClient
      .get<AccountBalanceResponse>(`/accounting/accounts/${id}/balance`, { params: { as_of_date: asOfDate } })
      .then((r) => r.data),

  create: (payload: AccountCreatePayload) =>
    apiClient.post<AccountPublic>("/accounting/accounts", payload).then((r) => r.data),

  update: (id: string, payload: AccountUpdatePayload) =>
    apiClient.patch<AccountPublic>(`/accounting/accounts/${id}`, payload).then((r) => r.data),
};
