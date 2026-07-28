import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type CounsellingCompletePayload,
  type CounsellingCreatePayload,
  counsellingApi,
} from "@/features/crm/counselling/api/counselling-api";

const counsellingKey = (leadId: string) => ["crm", "leads", leadId, "counselling"] as const;

export function useCounsellingSessions(leadId: string) {
  return useQuery({
    queryKey: counsellingKey(leadId),
    queryFn: () => counsellingApi.list(leadId),
    enabled: !!leadId,
  });
}

export function useCreateCounsellingSession(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CounsellingCreatePayload) => counsellingApi.create(leadId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: counsellingKey(leadId) }),
  });
}

export function useCompleteCounsellingSession(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionId,
      payload,
    }: {
      sessionId: string;
      payload: CounsellingCompletePayload;
    }) => counsellingApi.complete(leadId, sessionId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: counsellingKey(leadId) }),
  });
}

export function useDeleteCounsellingSession(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => counsellingApi.remove(leadId, sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: counsellingKey(leadId) }),
  });
}
