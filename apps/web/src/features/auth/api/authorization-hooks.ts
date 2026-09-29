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
  is_superuser: boolean;
}

// This admin app never self-gated on the caller's own roles/permissions
// before — GET /authorization/me existed only to look up *other* users'
// roles in the Roles panel. app-sidebar.tsx now filters every nav item
// against effective_permissions (mirroring apps/student-portal's own
// sidebar filter) and the 3 superuser-only items against is_superuser
// — see modules/authorization/service.py's _PLATFORM_ONLY_PERMISSIONS
// for the matching backend-side reasoning. This is what fixed an org-
// custom role (e.g. "ISE") seeing the entire admin menu instead of just
// what its own permissions actually cover.
export function useMyRoles() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: ["authorization", "me"],
    queryFn: () => apiClient.get<MyRolesResponse>("/authorization/me").then((r) => r.data),
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });
}
