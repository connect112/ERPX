import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type VAPTEngagementCreatePayload,
  type VAPTEngagementUpdatePayload,
  type VAPTFindingCreatePayload,
  type VAPTFindingUpdatePayload,
  vaptApi,
} from "@/features/corporate/vapt/api/vapt-api";
import type { FindingStatus } from "@/features/corporate/vapt/schemas/vapt-schemas";

const vaptKeys = {
  all: ["corporate", "vapt"] as const,
  byProject: (projectId: string) => [...vaptKeys.all, "project", projectId] as const,
  summary: (engagementId: string) => [...vaptKeys.all, engagementId, "summary"] as const,
  findings: (engagementId: string, status?: FindingStatus) =>
    [...vaptKeys.all, engagementId, "findings", status] as const,
};

export function useVAPTEngagementsByProject(projectId: string | undefined) {
  return useQuery({
    queryKey: vaptKeys.byProject(projectId ?? ""),
    queryFn: () => vaptApi.listByProject(projectId as string),
    enabled: !!projectId,
  });
}

export function useVAPTFindingsSummary(engagementId: string | undefined) {
  return useQuery({
    queryKey: vaptKeys.summary(engagementId ?? ""),
    queryFn: () => vaptApi.summary(engagementId as string),
    enabled: !!engagementId,
  });
}

export function useVAPTFindings(engagementId: string | undefined, status?: FindingStatus) {
  return useQuery({
    queryKey: vaptKeys.findings(engagementId ?? "", status),
    queryFn: () => vaptApi.listFindings(engagementId as string, status),
    enabled: !!engagementId,
  });
}

export function useCreateVAPTEngagement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VAPTEngagementCreatePayload) => vaptApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vaptKeys.all }),
  });
}

export function useUpdateVAPTEngagement(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VAPTEngagementUpdatePayload) => vaptApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vaptKeys.all }),
  });
}

export function useCreateVAPTFinding(engagementId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VAPTFindingCreatePayload) => vaptApi.createFinding(engagementId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vaptKeys.all }),
  });
}

export function useUpdateVAPTFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ findingId, payload }: { findingId: string; payload: VAPTFindingUpdatePayload }) =>
      vaptApi.updateFinding(findingId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vaptKeys.all }),
  });
}
