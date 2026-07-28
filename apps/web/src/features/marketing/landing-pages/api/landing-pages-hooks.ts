import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type LandingPageCreatePayload,
  type LandingPageListParams,
  type LandingPageUpdatePayload,
  landingPagesApi,
} from "@/features/marketing/landing-pages/api/landing-pages-api";

const landingPagesKeys = {
  all: ["marketing", "landing-pages"] as const,
  list: (params: LandingPageListParams) => [...landingPagesKeys.all, "list", params] as const,
  detail: (id: string) => [...landingPagesKeys.all, "detail", id] as const,
  stats: (id: string) => [...landingPagesKeys.all, id, "stats"] as const,
};

export function useLandingPagesList(params: LandingPageListParams) {
  return useQuery({
    queryKey: landingPagesKeys.list(params),
    queryFn: () => landingPagesApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useLandingPage(id: string | undefined) {
  return useQuery({
    queryKey: landingPagesKeys.detail(id ?? ""),
    queryFn: () => landingPagesApi.get(id as string),
    enabled: !!id,
  });
}

export function useLandingPageStats(id: string | undefined) {
  return useQuery({
    queryKey: landingPagesKeys.stats(id ?? ""),
    queryFn: () => landingPagesApi.stats(id as string),
    enabled: !!id,
  });
}

export function useCreateLandingPage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LandingPageCreatePayload) => landingPagesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: landingPagesKeys.all }),
  });
}

export function useUpdateLandingPage(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LandingPageUpdatePayload) => landingPagesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: landingPagesKeys.all }),
  });
}

export function usePublishLandingPage(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => landingPagesApi.publish(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: landingPagesKeys.all }),
  });
}

export function useArchiveLandingPage(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => landingPagesApi.archive(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: landingPagesKeys.all }),
  });
}
