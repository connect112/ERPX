import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AMCContractCreatePayload,
  type AMCContractListParams,
  type AMCContractUpdatePayload,
  type AMCVisitCreatePayload,
  amcApi,
} from "@/features/corporate/amc/api/amc-api";
import type { AMCVisitStatus } from "@/features/corporate/amc/schemas/amc-schemas";

const amcKeys = {
  all: ["corporate", "amc"] as const,
  list: (params: AMCContractListParams) => [...amcKeys.all, "list", params] as const,
  visits: (contractId: string, status?: AMCVisitStatus) =>
    [...amcKeys.all, contractId, "visits", status] as const,
};

export function useAMCContractsList(params: AMCContractListParams) {
  return useQuery({
    queryKey: amcKeys.list(params),
    queryFn: () => amcApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useAMCContractsDueForRenewal() {
  return useQuery({
    queryKey: [...amcKeys.all, "due-for-renewal"],
    queryFn: () => amcApi.listDueForRenewal(),
  });
}

export function useAMCVisits(contractId: string | undefined, status?: AMCVisitStatus) {
  return useQuery({
    queryKey: amcKeys.visits(contractId ?? "", status),
    queryFn: () => amcApi.listVisits(contractId as string, status),
    enabled: !!contractId,
  });
}

export function useCreateAMCContract() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AMCContractCreatePayload) => amcApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: amcKeys.all }),
  });
}

export function useUpdateAMCContract(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AMCContractUpdatePayload) => amcApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: amcKeys.all }),
  });
}

export function useCreateAMCVisit(contractId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AMCVisitCreatePayload) => amcApi.createVisit(contractId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: amcKeys.all }),
  });
}

export function useCompleteAMCVisit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ visitId, findings }: { visitId: string; findings: string }) =>
      amcApi.completeVisit(visitId, findings),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: amcKeys.all }),
  });
}

export function useCancelAMCVisit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (visitId: string) => amcApi.cancelVisit(visitId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: amcKeys.all }),
  });
}
