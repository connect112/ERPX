import { useQuery } from "@tanstack/react-query";

import { resolveHomePortal } from "@/features/auth/lib/portal-resolution";

// Cached for the session (staleTime effectively "don't refetch on every
// route change") — a person's access doesn't change mid-session, and this
// already costs up to 4 sequential requests in the worst case (someone
// resolving all the way down to "student").
export function useHomePortal(enabled: boolean) {
  return useQuery({
    queryKey: ["auth", "home-portal"],
    queryFn: () => resolveHomePortal(),
    enabled,
    staleTime: 5 * 60 * 1000,
  });
}
