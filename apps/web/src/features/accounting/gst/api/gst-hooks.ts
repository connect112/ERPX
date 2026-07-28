import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type GSTRateCreatePayload,
  type GSTRateUpdatePayload,
  gstApi,
} from "@/features/accounting/gst/api/gst-api";

const ratesKey = ["accounting", "gst", "rates"] as const;

export function useGSTRates(isActive?: boolean) {
  return useQuery({
    queryKey: [...ratesKey, isActive],
    queryFn: () => gstApi.listRates(isActive),
  });
}

export function useCreateGSTRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GSTRateCreatePayload) => gstApi.createRate(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ratesKey }),
  });
}

export function useUpdateGSTRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: GSTRateUpdatePayload }) =>
      gstApi.updateRate(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ratesKey }),
  });
}

export function useComputeTax() {
  return useMutation({
    mutationFn: ({
      taxableAmount,
      gstRateId,
      isInterstate,
    }: {
      taxableAmount: number;
      gstRateId: string;
      isInterstate: boolean;
    }) => gstApi.computeTax(taxableAmount, gstRateId, isInterstate),
  });
}

export function useGSTReturnSummary(periodFrom: string, periodTo: string, enabled: boolean) {
  return useQuery({
    queryKey: ["accounting", "gst", "returns", periodFrom, periodTo],
    queryFn: () => gstApi.getReturnSummary(periodFrom, periodTo),
    enabled,
  });
}
