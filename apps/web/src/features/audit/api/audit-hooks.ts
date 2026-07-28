import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { type AuditLogListParams, auditApi } from "@/features/audit/api/audit-api";

const auditKeys = {
  all: ["audit"] as const,
  list: (params: AuditLogListParams) => [...auditKeys.all, "list", params] as const,
  entityTypes: () => [...auditKeys.all, "entity-types"] as const,
};

export function useAuditLogsList(params: AuditLogListParams) {
  return useQuery({
    queryKey: auditKeys.list(params),
    queryFn: () => auditApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useAuditEntityTypes() {
  return useQuery({
    queryKey: auditKeys.entityTypes(),
    queryFn: () => auditApi.entityTypes(),
  });
}
