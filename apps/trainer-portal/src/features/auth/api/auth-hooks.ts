import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi, isTwoFactorRequired } from "@/features/auth/api/auth-api";
import { useAuthStore } from "@/store/auth-store";

export function useLoginMutation() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: { email: string; password: string; otp_code?: string }) =>
      authApi.login(payload),
    onSuccess: (data) => {
      if (isTwoFactorRequired(data)) return;
      // Same reason useLogout() clears the cache: every query is keyed
      // generically, not per-user. Without this, logging into a
      // *different* account in a tab that resolved the previous one's
      // home-portal within the last staleTime window gets served that
      // stale result — found live as a real admin login bouncing through
      // the wrong portal once before a fresh page load self-corrected it.
      queryClient.clear();
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
  const queryClient = useQueryClient();

  return async () => {
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // Best-effort server-side revocation; local logout proceeds regardless.
      }
    }
    logout();
    // Every query is keyed generically, not per-user — without this, a
    // second account logging in in the same tab right after can get
    // served the first account's cached results until each query's own
    // staleTime expires.
    queryClient.clear();
  };
}
