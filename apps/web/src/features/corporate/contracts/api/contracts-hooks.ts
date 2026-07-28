import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ContractCreatePayload,
  type ContractListParams,
  type ContractUpdatePayload,
  contractsApi,
} from "@/features/corporate/contracts/api/contracts-api";

const contractsKeys = {
  all: ["corporate", "contracts"] as const,
  list: (params: ContractListParams) => [...contractsKeys.all, "list", params] as const,
  expiring: (withinDays?: number) => [...contractsKeys.all, "expiring", withinDays] as const,
};

export function useContractsList(params: ContractListParams) {
  return useQuery({
    queryKey: contractsKeys.list(params),
    queryFn: () => contractsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useExpiringContracts(withinDays?: number) {
  return useQuery({
    queryKey: contractsKeys.expiring(withinDays),
    queryFn: () => contractsApi.listExpiring(withinDays),
  });
}

export function useCreateContract() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ContractCreatePayload) => contractsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: contractsKeys.all }),
  });
}

export function useUpdateContract(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ContractUpdatePayload) => contractsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: contractsKeys.all }),
  });
}

export function useActivateContract(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (signedDate: string) => contractsApi.activate(id, signedDate),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: contractsKeys.all }),
  });
}

export function useTerminateContract(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => contractsApi.terminate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: contractsKeys.all }),
  });
}

export function useRenewContract(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ newEndDate, newContractValue }: { newEndDate: string; newContractValue?: number }) =>
      contractsApi.renew(id, newEndDate, newContractValue),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: contractsKeys.all }),
  });
}

export function useMarkContractExpired(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => contractsApi.markExpired(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: contractsKeys.all }),
  });
}
