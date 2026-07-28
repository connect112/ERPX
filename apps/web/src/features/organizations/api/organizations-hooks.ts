import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type OrganizationCreatePayload,
  type OrganizationListParams,
  type OrganizationUpdatePayload,
  organizationsApi,
} from "@/features/organizations/api/organizations-api";

const organizationsKeys = {
  all: ["organizations"] as const,
  list: (params: OrganizationListParams) => [...organizationsKeys.all, "list", params] as const,
  detail: (id: string) => [...organizationsKeys.all, "detail", id] as const,
};

export function useOrganizationsList(params: OrganizationListParams) {
  return useQuery({
    queryKey: organizationsKeys.list(params),
    queryFn: () => organizationsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useOrganization(id: string | undefined) {
  return useQuery({
    queryKey: organizationsKeys.detail(id ?? ""),
    queryFn: () => organizationsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OrganizationCreatePayload) => organizationsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: organizationsKeys.all }),
  });
}

export function useUpdateOrganization(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OrganizationUpdatePayload) => organizationsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: organizationsKeys.all }),
  });
}

export function useDeleteOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => organizationsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: organizationsKeys.all }),
  });
}
