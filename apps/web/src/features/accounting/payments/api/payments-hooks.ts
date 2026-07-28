import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type PaymentCreatePayload,
  type PaymentListParams,
  paymentsApi,
} from "@/features/accounting/payments/api/payments-api";

const paymentsKeys = {
  all: ["accounting", "payments"] as const,
  list: (params: PaymentListParams) => [...paymentsKeys.all, "list", params] as const,
};

export function usePaymentsList(params: PaymentListParams) {
  return useQuery({
    queryKey: paymentsKeys.list(params),
    queryFn: () => paymentsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreatePayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PaymentCreatePayload) => paymentsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentsKeys.all }),
  });
}

export function useVoidPayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => paymentsApi.void(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: paymentsKeys.all }),
  });
}
