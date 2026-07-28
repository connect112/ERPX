import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type IntegrationCreatePayload,
  integrationsApi,
} from "@/features/integrations/api/integrations-api";

const integrationsKeys = {
  all: ["integrations"] as const,
  list: (params: { skip?: number; limit?: number }) => [...integrationsKeys.all, "list", params] as const,
};

export function useIntegrationsList(params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: integrationsKeys.list(params),
    queryFn: () => integrationsApi.list(params),
  });
}

export function useCreateIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: IntegrationCreatePayload) => integrationsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationsKeys.all }),
  });
}

export function useDeleteIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => integrationsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationsKeys.all }),
  });
}

export function useTestIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => integrationsApi.test(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: integrationsKeys.all }),
  });
}
