import { apiClient } from "@/api/client";
import type { AccountType } from "@/features/accounting/ledger/schemas/account-schemas";

export interface TrialBalanceLine {
  account_id: string;
  code: string;
  name: string;
  account_type: AccountType;
  debit_balance: number;
  credit_balance: number;
}

export interface TrialBalanceResponse {
  as_of_date: string;
  lines: TrialBalanceLine[];
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
}

export interface ProfitAndLossResponse {
  period_from: string;
  period_to: string;
  income_lines: TrialBalanceLine[];
  expense_lines: TrialBalanceLine[];
  total_income: number;
  total_expense: number;
  net_profit: number;
}

export interface BalanceSheetResponse {
  as_of_date: string;
  asset_lines: TrialBalanceLine[];
  liability_lines: TrialBalanceLine[];
  equity_lines: TrialBalanceLine[];
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  retained_earnings: number;
  total_liabilities_and_equity: number;
  is_balanced: boolean;
}

export interface AgingBucket {
  party_id: string;
  party_name: string;
  document_number: string;
  document_date: string;
  due_date: string;
  outstanding_amount: number;
  days_overdue: number;
  bucket: string;
}

export interface AgingReportResponse {
  as_of_date: string;
  items: AgingBucket[];
  total_outstanding: number;
  bucket_totals: Record<string, number>;
}

export const reportsApi = {
  trialBalance: (asOfDate: string) =>
    apiClient
      .get<TrialBalanceResponse>("/accounting/reports/trial-balance", { params: { as_of_date: asOfDate } })
      .then((r) => r.data),

  profitAndLoss: (periodFrom: string, periodTo: string) =>
    apiClient
      .get<ProfitAndLossResponse>("/accounting/reports/profit-and-loss", {
        params: { period_from: periodFrom, period_to: periodTo },
      })
      .then((r) => r.data),

  balanceSheet: (asOfDate: string) =>
    apiClient
      .get<BalanceSheetResponse>("/accounting/reports/balance-sheet", { params: { as_of_date: asOfDate } })
      .then((r) => r.data),

  arAging: (asOfDate: string) =>
    apiClient
      .get<AgingReportResponse>("/accounting/reports/aging/receivables", { params: { as_of_date: asOfDate } })
      .then((r) => r.data),

  apAging: (asOfDate: string) =>
    apiClient
      .get<AgingReportResponse>("/accounting/reports/aging/payables", { params: { as_of_date: asOfDate } })
      .then((r) => r.data),
};
