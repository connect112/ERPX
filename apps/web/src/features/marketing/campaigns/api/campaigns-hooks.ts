import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type CampaignCreatePayload,
  type CampaignListParams,
  type CampaignUpdatePayload,
  campaignsApi,
} from "@/features/marketing/campaigns/api/campaigns-api";
import type { CampaignStatus } from "@/features/marketing/campaigns/schemas/campaign-schemas";

const campaignsKeys = {
  all: ["marketing", "campaigns"] as const,
  list: (params: CampaignListParams) => [...campaignsKeys.all, "list", params] as const,
  detail: (id: string) => [...campaignsKeys.all, "detail", id] as const,
  performance: (id: string) => [...campaignsKeys.all, id, "performance"] as const,
};

export function useCampaignsList(params: CampaignListParams) {
  return useQuery({
    queryKey: campaignsKeys.list(params),
    queryFn: () => campaignsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCampaign(id: string | undefined) {
  return useQuery({
    queryKey: campaignsKeys.detail(id ?? ""),
    queryFn: () => campaignsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCampaignPerformance(id: string | undefined) {
  return useQuery({
    queryKey: campaignsKeys.performance(id ?? ""),
    queryFn: () => campaignsApi.performance(id as string),
    enabled: !!id,
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CampaignCreatePayload) => campaignsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: campaignsKeys.all }),
  });
}

export function useUpdateCampaign(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CampaignUpdatePayload) => campaignsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: campaignsKeys.all }),
  });
}

export function useChangeCampaignStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: CampaignStatus) => campaignsApi.changeStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: campaignsKeys.all }),
  });
}
