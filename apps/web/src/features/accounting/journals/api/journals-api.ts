import { apiClient } from "@/api/client";
import type {
  JournalEntryStatus,
  JournalSourceModule,
} from "@/features/accounting/journals/schemas/journal-schemas";

export interface JournalLinePublic {
  id: string;
  account_id: string;
  description: string | null;
  debit: number;
  credit: number;
  line_order: number;
}

export interface JournalEntryPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  entry_number: string;
  entry_date: string;
  memo: string | null;
  source_module: JournalSourceModule;
  source_id: string | null;
  status: JournalEntryStatus;
  reversed_by_entry_id: string | null;
  posted_at: string | null;
  created_at: string;
  lines: JournalLinePublic[];
}

export interface JournalListResponse {
  items: JournalEntryPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface JournalListParams {
  status?: JournalEntryStatus;
  source_module?: JournalSourceModule;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

export interface JournalLinePayload {
  account_id: string;
  description?: string;
  debit?: number;
  credit?: number;
}

export interface JournalEntryCreatePayload {
  entry_date: string;
  memo?: string;
  branch_id?: string;
  lines: JournalLinePayload[];
}

export const journalsApi = {
  list: (params: JournalListParams) =>
    apiClient.get<JournalListResponse>("/accounting/journals", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<JournalEntryPublic>(`/accounting/journals/${id}`).then((r) => r.data),

  create: (payload: JournalEntryCreatePayload) =>
    apiClient.post<JournalEntryPublic>("/accounting/journals", payload).then((r) => r.data),

  post: (id: string) =>
    apiClient.post<JournalEntryPublic>(`/accounting/journals/${id}/post`).then((r) => r.data),

  reverse: (id: string) =>
    apiClient.post<JournalEntryPublic>(`/accounting/journals/${id}/reverse`).then((r) => r.data),
};
