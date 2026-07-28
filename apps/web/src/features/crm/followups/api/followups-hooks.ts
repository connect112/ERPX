import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type FollowUpCompletePayload,
  type FollowUpCreatePayload,
  followupsApi,
} from "@/features/crm/followups/api/followups-api";

const followupsKey = (leadId: string) => ["crm", "leads", leadId, "followups"] as const;

export function useFollowUps(leadId: string) {
  return useQuery({
    queryKey: followupsKey(leadId),
    queryFn: () => followupsApi.list(leadId),
    enabled: !!leadId,
  });
}

export function useCreateFollowUp(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FollowUpCreatePayload) => followupsApi.create(leadId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: followupsKey(leadId) }),
  });
}

export function useCompleteFollowUp(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      followupId,
      payload,
    }: {
      followupId: string;
      payload: FollowUpCompletePayload;
    }) => followupsApi.complete(leadId, followupId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: followupsKey(leadId) }),
  });
}

export function useDeleteFollowUp(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (followupId: string) => followupsApi.remove(leadId, followupId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: followupsKey(leadId) }),
  });
}
