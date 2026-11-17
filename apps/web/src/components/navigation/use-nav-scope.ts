import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { useAuthStore } from "@/store/auth-store";

export type NavScope = { ready: false; userId: null; organizationId: null } | { ready: true; userId: string; organizationId: string | null };

/**
 * Whose browser preferences these are: the signed-in user and their organization. Not ready until both the user and the account's
 * details (GET /authorization/me, which the sidebar already needs) are known, so a preference is never read or written under a guess.
 */
export function useNavScope(): NavScope {
  const userId = useAuthStore((s) => s.user?.id ?? null);
  const { data } = useMyRoles();
  if (!userId || !data) return { ready: false, userId: null, organizationId: null };
  return { ready: true, userId, organizationId: data.organization_id ?? null };
}
