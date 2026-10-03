import { useQuery } from "@tanstack/react-query";

import { checkOwnership } from "@/lib/ownership-check";
import { useAuthStore } from "@/store/auth-store";

/**
 * Whether the signed-in account has a Student record. Same shape as
 * useIsTrainer()/useIsEmployee(): a 404 just means "not a student", not
 * an error, so it resolves to `false` rather than surfacing a
 * loading/error state.
 */
export function useIsStudent() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data, isLoading } = useQuery({
    queryKey: ["students", "me", "ownership-check"],
    queryFn: () => checkOwnership("/students/me"),
    retry: 3,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
  return { isStudent: data ?? false, isLoading };
}
