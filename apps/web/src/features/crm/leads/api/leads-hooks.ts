import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type LeadCreatePayload,
  type LeadListParams,
  type LeadStatusChangePayload,
  type LeadUpdatePayload,
  leadsApi,
} from "@/features/crm/leads/api/leads-api";

const leadsKeys = {
  all: ["crm", "leads"] as const,
  list: (params: LeadListParams) => [...leadsKeys.all, "list", params] as const,
  detail: (id: string) => [...leadsKeys.all, "detail", id] as const,
};

export function useLeadsList(params: LeadListParams) {
  return useQuery({
    queryKey: leadsKeys.list(params),
    queryFn: () => leadsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useLead(id: string | undefined) {
  return useQuery({
    queryKey: leadsKeys.detail(id ?? ""),
    queryFn: () => leadsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LeadCreatePayload) => leadsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: leadsKeys.all });
    },
  });
}

export function useUpdateLead(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LeadUpdatePayload) => leadsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: leadsKeys.all });
    },
  });
}

export function useChangeLeadStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LeadStatusChangePayload) => leadsApi.changeStatus(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: leadsKeys.all });
    },
  });
}

export function useDeleteLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => leadsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: leadsKeys.all });
    },
  });
}
