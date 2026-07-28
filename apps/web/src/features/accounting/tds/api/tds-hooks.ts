import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type TDSSectionCreatePayload,
  type TDSSectionUpdatePayload,
  tdsApi,
} from "@/features/accounting/tds/api/tds-api";

const sectionsKey = ["accounting", "tds", "sections"] as const;

export function useTDSSections(isActive?: boolean) {
  return useQuery({
    queryKey: [...sectionsKey, isActive],
    queryFn: () => tdsApi.listSections(isActive),
  });
}

export function useCreateTDSSection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TDSSectionCreatePayload) => tdsApi.createSection(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sectionsKey }),
  });
}

export function useUpdateTDSSection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: TDSSectionUpdatePayload }) =>
      tdsApi.updateSection(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sectionsKey }),
  });
}

export function useTDSDeductionsForVendor(vendorId: string) {
  return useQuery({
    queryKey: ["accounting", "tds", "deductions", vendorId],
    queryFn: () => tdsApi.listDeductionsForVendor(vendorId),
    enabled: !!vendorId,
  });
}
