import { useQuery } from "@tanstack/react-query";

import { checkOwnership } from "@/lib/ownership-check";
import { useAuthStore } from "@/store/auth-store";

/**
 * Whether the signed-in account has a Trainer record — the same
 * ownership check every trainer-only backend endpoint already applies
 * (modules/trainers/dependencies.py), used here only to decide whether
 * the sidebar shows the "My Work" section. A 404 means "not a trainer",
 * not an error, so it resolves to `false` rather than surfacing a
 * loading/error state — most accounts (admins, students) simply aren't
 * trainers, and the sidebar item should just quietly not appear for them.
 */
export function useIsTrainer() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { data, isLoading } = useQuery({
    queryKey: ["trainers", "me", "ownership-check"],
    queryFn: () => checkOwnership("/trainers/me"),
    retry: 3,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
  return { isTrainer: data ?? false, isLoading };
}
