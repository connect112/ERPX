import { useMutation, useQuery } from "@tanstack/react-query";

import { authApi, isTwoFactorRequired } from "@/features/auth/api/auth-api";
import { useAuthStore } from "@/store/auth-store";

export function useLoginMutation() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  return useMutation({
    mutationFn: (payload: { email: string; password: string; otp_code?: string }) =>
      authApi.login(payload),
    onSuccess: (data) => {
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
