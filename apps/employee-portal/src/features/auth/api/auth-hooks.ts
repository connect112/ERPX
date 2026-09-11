import { useMutation, useQuery } from "@tanstack/react-query";

import { authApi, isTwoFactorRequired } from "@/features/auth/api/auth-api";
import { useAuthStore } from "@/store/auth-store";

export function useLoginMutation() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);
  const setPermissions = useAuthStore((s) => s.setPermissions);

  return useMutation({
    mutationFn: (payload: { email: string; password: string; otp_code?: string }) =>
      authApi.login(payload),
    onSuccess: async (data) => {
      if (isTwoFactorRequired(data)) return;
      setTokens(data.access_token, data.refresh_token);
      setUser({
        id: data.user.id,
        email: data.user.email,
        fullName: data.user.full_name,
        status: data.user.status,
        isEmailVerified: data.user.is_email_verified,
        twoFactorEnabled: data.user.two_factor_enabled,
      });
      // Fetched once here (not left to a background query) so the very
      // first render of the app shell after login already has the real
      // permission set — nav items never flash in and then disappear.
      try {
        const { effective_permissions } = await authApi.myRoles();
        setPermissions(effective_permissions);
      } catch {
        // Non-fatal: the SPA falls back to showing nothing permission-gated
        // rather than blocking login on this call. Server-side authorization
        // is the real enforcement boundary regardless.
        setPermissions([]);
      }
    },
  });
}

export function useCurrentUser() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => authApi.me(),
    enabled: isAuthenticated,
  });
}

export function useResetPasswordMutation() {
  return useMutation({
    mutationFn: (payload: { token: string; new_password: string }) => authApi.resetPassword(payload),
  });
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout);
  const refreshToken = useAuthStore((s) => s.refreshToken);

  return async () => {
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // Best-effort server-side revocation; local logout proceeds regardless.
      }
    }
    logout();
  };
}
