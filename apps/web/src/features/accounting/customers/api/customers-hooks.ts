import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type CustomerCreatePayload,
  type CustomerListParams,
  type CustomerUpdatePayload,
  customersApi,
} from "@/features/accounting/customers/api/customers-api";

const customersKeys = {
  all: ["accounting", "customers"] as const,
  list: (params: CustomerListParams) => [...customersKeys.all, "list", params] as const,
  detail: (id: string) => [...customersKeys.all, "detail", id] as const,
};

export function useCustomersList(params: CustomerListParams) {
  return useQuery({
    queryKey: customersKeys.list(params),
    queryFn: () => customersApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCustomer(id: string | undefined) {
  return useQuery({
    queryKey: customersKeys.detail(id ?? ""),
    queryFn: () => customersApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CustomerCreatePayload) => customersApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: customersKeys.all }),
  });
}

export function useUpdateCustomer(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CustomerUpdatePayload) => customersApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: customersKeys.all }),
  });
}

export function useDeleteCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => customersApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: customersKeys.all }),
  });
}
