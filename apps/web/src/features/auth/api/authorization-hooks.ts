import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import { useAuthStore } from "@/store/auth-store";

interface RolePublic {
  id: string;
  name: string;
  slug: string;
}

interface MyRolesResponse {
  user_id: string;
  roles: RolePublic[];
  effective_permissions: string[];
}

// This admin app never self-gated on the caller's own roles/permissions
// before — GET /authorization/me existed only to look up *other* users'
// roles in the Roles panel. app-sidebar.tsx now uses this to hide the
// Business Modules section from platform-operator (Super Admin) accounts
// — see modules/authorization/service.py's _PLATFORM_ONLY_PERMISSIONS for
// the matching backend-side reasoning.
export function useMyRoles() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: ["authorization", "me"],
    queryFn: () => apiClient.get<MyRolesResponse>("/authorization/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
}
