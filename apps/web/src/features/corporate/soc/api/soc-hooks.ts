import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type SOCIncidentCreatePayload,
  type SOCIncidentUpdatePayload,
  type SOCServiceCreatePayload,
  type SOCServiceUpdatePayload,
  socApi,
} from "@/features/corporate/soc/api/soc-api";
import type { IncidentStatus, SOCServiceStatus } from "@/features/corporate/soc/schemas/soc-schemas";

const socKeys = {
  all: ["corporate", "soc"] as const,
  byClient: (clientId: string, status?: SOCServiceStatus) => [...socKeys.all, "client", clientId, status] as const,
  incidents: (serviceId: string, status?: IncidentStatus) =>
    [...socKeys.all, serviceId, "incidents", status] as const,
};

export function useSOCServicesByClient(clientId: string | undefined, status?: SOCServiceStatus) {
  return useQuery({
    queryKey: socKeys.byClient(clientId ?? "", status),
    queryFn: () => socApi.listByClient(clientId as string, status),
    enabled: !!clientId,
  });
}

export function useSOCIncidents(serviceId: string | undefined, status?: IncidentStatus) {
  return useQuery({
    queryKey: socKeys.incidents(serviceId ?? "", status),
    queryFn: () => socApi.listIncidents(serviceId as string, status),
    enabled: !!serviceId,
  });
}

export function useCreateSOCService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SOCServiceCreatePayload) => socApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: socKeys.all }),
  });
}

export function useUpdateSOCService(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SOCServiceUpdatePayload) => socApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: socKeys.all }),
  });
}

export function useCreateSOCIncident(serviceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SOCIncidentCreatePayload) => socApi.createIncident(serviceId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: socKeys.all }),
  });
}

export function useUpdateSOCIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ incidentId, payload }: { incidentId: string; payload: SOCIncidentUpdatePayload }) =>
      socApi.updateIncident(incidentId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: socKeys.all }),
  });
}
