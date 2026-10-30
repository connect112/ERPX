import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

/** The kinds of documents the server can bulk-download (modules/bulk_exports/sources). */
export type BulkSource = "exam_certificates" | "internship_certificates" | "offer_letters" | "payslips" | "documents";

export interface Placeholder {
  key: string;
  label: string;
  example: string;
  custom: boolean;
}

export interface Option {
  value: string;
  label: string;
}

export interface Preset {
  label: string;
  template: string;
}

export interface SourceInfo {
  source: BulkSource;
  label: string;
  document_type: string;
  scope_id: string | null;
  scope_label: string;
  extension: string | null;
  placeholders: Placeholder[];
  zip_placeholders: Placeholder[];
  status_options: Option[];
  presets: Preset[];
  folder_presets: Preset[];
  default_zip_template: string;
  max_items: number;
}

export interface BulkItem {
  id: string;
  title: string;
  subtitle: string;
  status: string | null;
}

export interface ItemsPage {
  items: BulkItem[];
  total: number;
  page: number;
  page_size: number;
}

export type SelectionPayload =
  | { mode: "selected"; ids: string[] }
  | { mode: "filtered"; search?: string; status?: string; exclude_ids: string[] };

export interface NamingOptions {
  filename_template: string;
  folder_template?: string;
  zip_template?: string;
}

export interface PreviewResult {
  valid: boolean;
  error: string | null;
  zip_filename: string | null;
  total: number;
  files: { id: string; title: string; path: string; missing: string[] }[];
  warnings: string[];
  renamed_duplicates: number;
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "expired";

export interface BulkJob {
  id: string;
  source: BulkSource;
  source_label: string;
  scope_id: string | null;
  scope_label: string;
  status: JobStatus;
  selection_mode: string;
  options: NamingOptions;
  total_items: number;
  processed_items: number;
  failed_items: number;
  failures: { id: string; title: string; error: string }[];
  zip_filename: string | null;
  size_bytes: number | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  expires_at: string | null;
  download_count: number;
}

export interface ItemFilters {
  search?: string;
  status?: string;
  page: number;
  pageSize: number;
}

const BASE = "/bulk-exports";

export const bulkDownloadsApi = {
  source: (source: BulkSource, scopeId: string | null) =>
    apiClient.get<SourceInfo>(`${BASE}/sources/${source}`, { params: { scope_id: scopeId ?? undefined } }).then((r) => r.data),
  items: (source: BulkSource, scopeId: string | null, f: ItemFilters) =>
    apiClient
      .get<ItemsPage>(`${BASE}/sources/${source}/items`, {
        params: {
          scope_id: scopeId ?? undefined,
          search: f.search || undefined,
          status: f.status || undefined,
          page: f.page,
          page_size: f.pageSize,
        },
      })
      .then((r) => r.data),
  preview: (source: BulkSource, scopeId: string | null, options: NamingOptions, selection: SelectionPayload | null) =>
    apiClient
      .post<PreviewResult>(`${BASE}/preview`, { source, scope_id: scopeId, options, selection })
      .then((r) => r.data),
  create: (source: BulkSource, scopeId: string | null, selection: SelectionPayload, options: NamingOptions) =>
    apiClient.post<BulkJob>(`${BASE}/jobs`, { source, scope_id: scopeId, selection, options }).then((r) => r.data),
  jobs: () => apiClient.get<BulkJob[]>(`${BASE}/jobs`).then((r) => r.data),
  job: (id: string) => apiClient.get<BulkJob>(`${BASE}/jobs/${id}`).then((r) => r.data),
  cancel: (id: string) => apiClient.post<BulkJob>(`${BASE}/jobs/${id}/cancel`).then((r) => r.data),
  discard: (id: string) => apiClient.delete<BulkJob>(`${BASE}/jobs/${id}/file`).then((r) => r.data),
  downloadLink: (id: string) =>
    apiClient.post<{ url: string; filename: string; expires_in_seconds: number }>(`${BASE}/jobs/${id}/download`).then((r) => r.data),
};

/** Ask for a short-lived link and let the browser save the ZIP (the file comes straight from storage). */
export async function downloadJob(id: string): Promise<void> {
  const { url, filename } = await bulkDownloadsApi.downloadLink(id);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export const isActive = (status: JobStatus) => status === "queued" || status === "running";

export function useSourceInfo(source: BulkSource, scopeId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["bulk-downloads", "source", source, scopeId],
    queryFn: () => bulkDownloadsApi.source(source, scopeId),
    enabled,
    staleTime: 60_000,
  });
}

export function useBulkItems(source: BulkSource, scopeId: string | null, filters: ItemFilters, enabled: boolean) {
  return useQuery({
    queryKey: ["bulk-downloads", "items", source, scopeId, filters],
    queryFn: () => bulkDownloadsApi.items(source, scopeId, filters),
    enabled,
    placeholderData: (previous) => previous,
  });
}

/** One job, polled every two seconds while it is being prepared. */
export function useBulkJob(id: string | null) {
  return useQuery({
    queryKey: ["bulk-downloads", "job", id],
    queryFn: () => bulkDownloadsApi.job(id as string),
    enabled: id !== null,
    refetchInterval: (query) => (query.state.data && isActive(query.state.data.status) ? 2000 : false),
  });
}

export function useBulkJobs() {
  return useQuery({
    queryKey: ["bulk-downloads", "jobs"],
    queryFn: bulkDownloadsApi.jobs,
    refetchInterval: (query) => (query.state.data?.some((j) => isActive(j.status)) ? 3000 : false),
  });
}

export function useJobAction(action: (id: string) => Promise<BulkJob>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: action,
    onSuccess: (job) => {
      queryClient.setQueryData(["bulk-downloads", "job", job.id], job);
      void queryClient.invalidateQueries({ queryKey: ["bulk-downloads", "jobs"] });
    },
  });
}
