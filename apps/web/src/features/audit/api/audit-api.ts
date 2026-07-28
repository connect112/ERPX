import { apiClient } from "@/api/client";

export type AuditAction = "create" | "update" | "delete";

export interface AuditChangeValue {
  old: unknown;
  new: unknown;
}

export interface AuditLogPublic {
  id: string;
  organization_id: string | null;
  user_id: string | null;
  user_email: string | null;
  user_full_name: string | null;
  action: AuditAction;
  entity_type: string;
  entity_id: string | null;
  changes: Record<string, AuditChangeValue | unknown>;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogPublic[];
  total: number;
}

export interface AuditLogListParams {
  entity_type?: string;
  entity_id?: string;
  user_id?: string;
  action?: AuditAction;
  since?: string;
  until?: string;
  skip?: number;
  limit?: number;
}

export const auditApi = {
  list: (params: AuditLogListParams) =>
    apiClient.get<AuditLogListResponse>("/audit", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<AuditLogPublic>(`/audit/${id}`).then((r) => r.data),

  entityTypes: () => apiClient.get<string[]>("/audit/entity-types").then((r) => r.data),
};
