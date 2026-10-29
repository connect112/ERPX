import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

const base = "/pentrix-ops";

export type PaymentGroup = "pending" | "paid" | "failed" | "refunded" | "partially_refunded";

export interface Payment {
  id: string;
  pentrix_payment_id: string;
  candidate_id: string | null;
  candidate_name: string;
  candidate_email: string;
  provider: string;
  /** Pentrix records the payment provider, not the instrument (card, UPI...), so that is what this shows. */
  method: string;
  purpose: string;
  purpose_label: string;
  amount_paise: number;
  currency: string;
  status: PaymentGroup;
  status_label: string;
  pentrix_status: string;
  reference: string | null;
  provider_order_id: string | null;
  invoice_number: string | null;
  receipt_number: string | null;
  provisioning_status: string | null;
  created_at: string | null;
  paid_at: string | null;
  failed_at: string | null;
  refunded_at: string | null;
  invoice_available: boolean;
}

export interface PaymentPage {
  items: Payment[];
  total: number;
  page: number;
  page_size: number;
}

export interface SyncState {
  configured: boolean;
  last_synced_at: string | null;
  last_error: string | null;
}

export interface PaymentsSummary {
  date: string;
  collected_today_paise: number;
  successful_today: number;
  refunded_today_paise: number;
  pending_payments: number;
  latest_payment: Payment | null;
  recent: Payment[];
  sync: SyncState;
}

export type DayStatus = "matched" | "mismatch" | "error" | "open" | "unreconciled";

export interface Difference {
  kind: string;
  payment_id: string | null;
  detail: string;
}

export interface DailySummary {
  date: string;
  status: DayStatus;
  reconciled: boolean;
  reconciled_at: string | null;
  successful_count: number;
  collected_paise: number;
  pending_count: number;
  failed_count: number;
  refund_count: number;
  refunded_paise: number;
  partial_refund_count: number;
  net_paise: number;
  mismatches: Difference[];
  repaired_count: number;
  attempts: number;
  last_error: string | null;
}

export interface DailyDetail {
  summary: DailySummary;
  transactions: Payment[];
}

export interface PaymentFilters {
  q: string;
  status: string;
  purpose: string;
  date_from: string;
  date_to: string;
  sort: string;
  order: "asc" | "desc";
  page: number;
  /** A Pentrix candidate id: used on a candidate's own page. */
  candidate?: string;
}

export const EMPTY_PAYMENT_FILTERS: PaymentFilters = { q: "", status: "", purpose: "", date_from: "", date_to: "", sort: "date", order: "desc", page: 1 };

export const paymentKeys = {
  list: (f: PaymentFilters) => ["pentrix-ops", "payments", f] as const,
  summary: ["pentrix-ops", "payments", "summary"] as const,
  daily: (from: string, to: string) => ["pentrix-ops", "payments", "daily", from, to] as const,
  day: (day: string) => ["pentrix-ops", "payments", "day", day] as const,
};

/** Chosen as whole days in India: from the start of the first day to the end of the last. */
export function paymentParams(f: PaymentFilters, pageSize = 25): URLSearchParams {
  const p = new URLSearchParams();
  const add = (key: string, value: string | undefined) => value && p.append(key, value);
  add("q", f.q);
  add("status", f.status);
  add("purpose", f.purpose);
  add("candidate", f.candidate);
  if (f.date_from) p.append("date_from", new Date(`${f.date_from}T00:00:00+05:30`).toISOString());
  if (f.date_to) p.append("date_to", new Date(new Date(`${f.date_to}T00:00:00+05:30`).getTime() + 86_400_000).toISOString());
  p.append("sort", f.sort);
  p.append("order", f.order);
  p.append("page", String(f.page));
  p.append("page_size", String(pageSize));
  return p;
}

export const paymentsApi = {
  list: (f: PaymentFilters, pageSize = 25) => apiClient.get<PaymentPage>(`${base}/payments`, { params: paymentParams(f, pageSize) }).then((r) => r.data),
  summary: () => apiClient.get<PaymentsSummary>(`${base}/payments/summary`).then((r) => r.data),
  sync: () => apiClient.post<{ updated: number }>(`${base}/payments/sync`).then((r) => r.data),
  daily: (from: string, to: string) => apiClient.get<DailySummary[]>(`${base}/payments/daily`, { params: { date_from: from, date_to: to } }).then((r) => r.data),
  day: (day: string) => apiClient.get<DailyDetail>(`${base}/payments/daily/${day}`).then((r) => r.data),
  reconcile: (day: string) => apiClient.post<DailySummary>(`${base}/payments/daily/${day}/reconcile`).then((r) => r.data),
};

/** Fetch a file the server makes (an invoice, a CSV) with the signed-in session, then show or save it. */
export async function openFile(path: string, filename: string, mode: "view" | "save"): Promise<void> {
  const response = await apiClient.get<Blob>(`${base}${path}`, { responseType: "blob", params: mode === "save" ? { download: true } : undefined });
  const url = URL.createObjectURL(response.data);
  if (mode === "view") {
    window.open(url, "_blank", "noopener");
  } else {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const usePayments = (f: PaymentFilters, pageSize = 25, enabled = true) =>
  useQuery({ queryKey: [...paymentKeys.list(f), pageSize], queryFn: () => paymentsApi.list(f, pageSize), refetchInterval: 60_000, enabled });
export const usePaymentsSummary = (enabled = true) =>
  useQuery({ queryKey: paymentKeys.summary, queryFn: paymentsApi.summary, refetchInterval: 60_000, enabled, retry: false });
export const useDailySummaries = (from: string, to: string) => useQuery({ queryKey: paymentKeys.daily(from, to), queryFn: () => paymentsApi.daily(from, to) });
export const useDay = (day: string | null) => useQuery({ queryKey: paymentKeys.day(day ?? ""), queryFn: () => paymentsApi.day(day as string), enabled: !!day });
