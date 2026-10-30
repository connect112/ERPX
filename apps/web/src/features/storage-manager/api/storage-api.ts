import { apiClient } from "@/api/client";

export type FileStatus = "in_use" | "pending" | "orphan" | "missing_object" | "protected";

export interface FileItem {
  id: string;
  source: string;
  source_label: string;
  module: string;
  backend: "object_storage" | "database";
  name: string;
  path: string[];
  size_bytes: number;
  content_type: string | null;
  type_group: string;
  created_at: string | null;
  owner: string | null;
  organization_id: string | null;
  organization_name: string | null;
  location: string;
  status: FileStatus;
  protected: boolean;
  protected_reason: string | null;
  fingerprint: string | null;
  is_large: boolean;
  previewable: string | null;
}

export interface FolderItem {
  name: string;
  path: string[];
  file_count: number;
  total_bytes: number;
}

export interface FileListResponse {
  items: FileItem[];
  folders: FolderItem[];
  path: string[];
  total: number;
  page: number;
  page_size: number;
  total_bytes: number;
  flat: boolean;
  subtree_count: number;
  subtree_bytes: number;
}

export interface FileFilters {
  path: string[];
  q?: string;
  source?: string;
  status?: string;
  type_group?: string;
  min_size?: number;
  owner?: string;
  large?: boolean;
  sort: string;
  order: "asc" | "desc";
  page: number;
  page_size: number;
}

export interface Evidence {
  kind: "record" | "reference" | "protected" | "note";
  text: string;
  module: string | null;
  record_id: string | null;
}

export interface Analysis {
  item: FileItem;
  verdict: "eligible" | "in_use" | "protected" | "not_deletable" | "missing";
  can_delete: boolean;
  reasons: string[];
  evidence: Evidence[];
}

export interface DuplicateGroup {
  fingerprint: string;
  size_bytes: number;
  count: number;
  wasted_bytes: number;
  files: FileItem[];
}

export interface SourceUsage {
  key: string;
  label: string;
  backend: string;
  count: number;
  bytes: number;
  protected: boolean;
}

export interface FilesUsage {
  total_count: number;
  total_bytes: number;
  by_source: SourceUsage[];
  by_type: { type_group: string; count: number; bytes: number }[];
  orphan_count: number;
  orphan_bytes: number;
  large_count: number;
  large_bytes: number;
  duplicate_groups: number;
  duplicate_wasted_bytes: number;
  protected_count: number;
  protected_bytes: number;
  trash_count: number;
  trash_bytes: number;
}

export interface UsageResponse {
  generated_at: string;
  scope: "organization" | "platform";
  files: FilesUsage;
  can_delete: boolean;
}

export interface DeletionPreview {
  items: Analysis[];
  eligible_count: number;
  blocked_count: number;
  total_bytes: number;
  confirm_text: string;
}

export interface TrashItem {
  id: string;
  organization_id: string | null;
  source: string;
  original_key: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  reason: string;
  deleted_by: string | null;
  deleted_at: string;
  purge_allowed_at: string;
  can_purge: boolean;
  restored_at: string | null;
  purged_at: string | null;
  evidence: Evidence[];
}

export interface TrashList {
  items: TrashItem[];
  total: number;
  total_bytes: number;
  min_days: number;
}

export interface DeletionLogItem {
  id: string;
  created_at: string;
  action: "trash" | "restore" | "purge";
  source: string;
  object_key: string;
  filename: string | null;
  size_bytes: number | null;
  user_email: string | null;
  reason: string | null;
  ip_address: string | null;
  evidence: Evidence[];
  trash_id: string | null;
}

export interface PreviewResponse {
  kind: "image" | "pdf" | "video" | "text" | null;
  mode: "url" | "content" | "none";
  url: string | null;
  content_type: string | null;
  expires_in: number | null;
  message: string | null;
}

export interface ServerStatus {
  generated_at: string;
  database: { name: string; total_bytes: number; top_tables: { table: string; bytes: number }[] };
  object_storage: {
    bucket: string;
    object_count: number;
    total_bytes: number;
    in_app_backups_bytes: number;
    trash_bytes: number;
  };
  host: {
    available: boolean;
    reason?: string;
    checked_at?: string;
    disk_total_bytes?: number;
    disk_free_bytes?: number;
    alerts?: { name: string; severity: string; message: string }[];
    docker_df?: { Type: string; TotalCount: string; Size: string; Reclaimable: string }[];
  };
}

const BASE = "/storage-manager";

export const storageApi = {
  files: (filters: FileFilters) =>
    apiClient
      .get<FileListResponse>(`${BASE}/files`, {
        params: { ...filters, path: filters.path.join("/") },
      })
      .then((r) => r.data),

  usage: () => apiClient.get<UsageResponse>(`${BASE}/usage`).then((r) => r.data),
  duplicates: () => apiClient.get<DuplicateGroup[]>(`${BASE}/duplicates`).then((r) => r.data),
  server: () => apiClient.get<ServerStatus>(`${BASE}/server`).then((r) => r.data),
  analysis: (id: string) => apiClient.get<Analysis>(`${BASE}/analysis`, { params: { id } }).then((r) => r.data),

  preview: (id: string, download = false) =>
    apiClient.get<PreviewResponse>(`${BASE}/preview`, { params: { id, download } }).then((r) => r.data),

  // A file kept inside the database comes back through an authenticated request, as a blob.
  content: (url: string) =>
    apiClient.get<Blob>(url.replace(/^\/api\/v1/, ""), { responseType: "blob" }).then((r) => r.data),

  previewDeletion: (ids: string[]) =>
    apiClient.post<DeletionPreview>(`${BASE}/deletions/preview`, { ids }).then((r) => r.data),

  deleteFiles: (body: { ids: string[]; reason: string; confirm_text: string }) =>
    apiClient.post<{ moved: TrashItem[]; total_bytes: number }>(`${BASE}/deletions`, body).then((r) => r.data),

  trash: (includeClosed = false) =>
    apiClient.get<TrashList>(`${BASE}/trash`, { params: { include_closed: includeClosed } }).then((r) => r.data),

  restore: (id: string) => apiClient.post<TrashItem>(`${BASE}/trash/${id}/restore`).then((r) => r.data),

  purge: (body: { ids: string[]; confirm_text: string }) =>
    apiClient.post<TrashItem[]>(`${BASE}/trash/purge`, body).then((r) => r.data),

  log: (skip: number, limit: number) =>
    apiClient
      .get<{ items: DeletionLogItem[]; total: number }>(`${BASE}/deletion-log`, { params: { skip, limit } })
      .then((r) => r.data),
};
