import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type InvoiceCreatePayload,
  type InvoiceListParams,
  invoicesApi,
} from "@/features/accounting/invoices/api/invoices-api";

const invoicesKeys = {
  all: ["accounting", "invoices"] as const,
  list: (params: InvoiceListParams) => [...invoicesKeys.all, "list", params] as const,
  detail: (id: string) => [...invoicesKeys.all, "detail", id] as const,
};

export function useInvoicesList(params: InvoiceListParams) {
  return useQuery({
    queryKey: invoicesKeys.list(params),
    queryFn: () => invoicesApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useInvoice(id: string | undefined) {
  return useQuery({
    queryKey: invoicesKeys.detail(id ?? ""),
    queryFn: () => invoicesApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InvoiceCreatePayload) => invoicesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invoicesKeys.all }),
  });
}

export function usePostInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => invoicesApi.post(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invoicesKeys.all }),
  });
}

export function useCancelInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => invoicesApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invoicesKeys.all }),
  });
}
