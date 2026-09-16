import { useQuery } from "@tanstack/react-query";

import { authApi } from "@/features/auth/api/auth-api";
import { useAuthStore } from "@/store/auth-store";

/**
 * Silent cross-subdomain login. Runs only when this origin's own
 * localStorage has no session (`enabled` is `!isAuthenticated` — see
 * ProtectedRoute) and asks the API whether the shared `erpx_sso` cookie
 * (set at /login on *any* ERPX subdomain — see
 * modules/authentication/routes.py) can stand one up here instead of
 * showing the login page. A 401 (no cookie, or an invalid/expired one)
 * just means "no session" — ProtectedRoute falls through to the normal
 * /login redirect, not an error state.
 */
export function useSsoBootstrap(enabled: boolean) {
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  return useQuery({
    queryKey: ["auth", "sso-bootstrap"],
    queryFn: async () => {
      const data = await authApi.ssoBootstrap();
      setTokens(data.access_token, data.refresh_token);
      setUser({
        id: data.user.id,
        email: data.user.email,
        fullName: data.user.full_name,
        status: data.user.status,
        isEmailVerified: data.user.is_email_verified,
        twoFactorEnabled: data.user.two_factor_enabled,
      });
      return true;
    },
    enabled,
    retry: false,
    staleTime: Infinity,
  });
}
