import { useQuery } from "@tanstack/react-query";

import { checkOwnership } from "@/lib/ownership-check";
import { useAuthStore } from "@/store/auth-store";

/**
 * Whether the signed-in account has an Employee record — every trainer
 * has one too (Trainer is layered on Employee), so this covers both.
 * Same shape as useIsTrainer(): a 404 just means "not an employee", not
 * an error, so it resolves to `false` rather than surfacing a
 * loading/error state.
 */
export function useIsEmployee() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data, isLoading } = useQuery({
    queryKey: ["employees", "me", "ownership-check"],
    queryFn: () => checkOwnership("/employees/me"),
    retry: 3,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
  return { isEmployee: data ?? false, isLoading };
}
