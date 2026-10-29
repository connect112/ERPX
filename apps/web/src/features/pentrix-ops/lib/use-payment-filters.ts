import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { EMPTY_PAYMENT_FILTERS, type PaymentFilters } from "@/features/pentrix-ops/api/payments-api";

const KEYS = ["q", "status", "purpose", "date_from", "date_to", "sort", "order"] as const;

/** The payment filters live in the address, so a link opens the list already narrowed. */
export function usePaymentFilters() {
  const [params, setParams] = useSearchParams();
  const filters = useMemo<PaymentFilters>(() => {
    const next: PaymentFilters = { ...EMPTY_PAYMENT_FILTERS, page: Math.max(Number(params.get("page")) || 1, 1) };
    for (const key of KEYS) {
      const value = params.get(key);
      if (value) (next as unknown as Record<string, string>)[key] = value;
    }
    return next;
  }, [params]);

  function update(patch: Partial<PaymentFilters>) {
    const merged: PaymentFilters = { ...filters, ...patch, page: patch.page ?? 1 };
    const next = new URLSearchParams();
    for (const key of KEYS) {
      const value = merged[key];
      if (value && value !== EMPTY_PAYMENT_FILTERS[key]) next.set(key, value);
    }
    if (merged.page > 1) next.set("page", String(merged.page));
    setParams(next, { replace: true });
  }

  return { filters, update, clear: () => setParams(new URLSearchParams(), { replace: true }), active: KEYS.some((k) => params.get(k) && params.get(k) !== EMPTY_PAYMENT_FILTERS[k]) };
}
