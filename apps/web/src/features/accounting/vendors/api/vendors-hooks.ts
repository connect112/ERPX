import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type VendorCreatePayload,
  type VendorListParams,
  type VendorUpdatePayload,
  vendorsApi,
} from "@/features/accounting/vendors/api/vendors-api";

const vendorsKeys = {
  all: ["accounting", "vendors"] as const,
  list: (params: VendorListParams) => [...vendorsKeys.all, "list", params] as const,
  detail: (id: string) => [...vendorsKeys.all, "detail", id] as const,
};

export function useVendorsList(params: VendorListParams) {
  return useQuery({
    queryKey: vendorsKeys.list(params),
    queryFn: () => vendorsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useVendor(id: string | undefined) {
  return useQuery({
    queryKey: vendorsKeys.detail(id ?? ""),
    queryFn: () => vendorsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateVendor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VendorCreatePayload) => vendorsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vendorsKeys.all }),
  });
}

export function useUpdateVendor(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VendorUpdatePayload) => vendorsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vendorsKeys.all }),
  });
}

export function useDeleteVendor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => vendorsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: vendorsKeys.all }),
  });
}
