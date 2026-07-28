import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ClientCreatePayload,
  type ClientListParams,
  type ClientUpdatePayload,
  clientsApi,
} from "@/features/corporate/clients/api/clients-api";
import type { ClientStatus } from "@/features/corporate/clients/schemas/client-schemas";

const clientsKeys = {
  all: ["corporate", "clients"] as const,
  list: (params: ClientListParams) => [...clientsKeys.all, "list", params] as const,
  detail: (id: string) => [...clientsKeys.all, "detail", id] as const,
};

export function useClientsList(params: ClientListParams) {
  return useQuery({
    queryKey: clientsKeys.list(params),
    queryFn: () => clientsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useClient(id: string | undefined) {
  return useQuery({
    queryKey: clientsKeys.detail(id ?? ""),
    queryFn: () => clientsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ClientCreatePayload) => clientsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: clientsKeys.all }),
  });
}

export function useUpdateClient(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ClientUpdatePayload) => clientsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: clientsKeys.all }),
  });
}

export function useChangeClientStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: ClientStatus) => clientsApi.changeStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: clientsKeys.all }),
  });
}

export function useDeleteClient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => clientsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: clientsKeys.all }),
  });
}
