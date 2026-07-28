import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi, isTwoFactorRequired } from "@/features/auth/api/auth-api";
import { useAuthStore } from "@/store/auth-store";

const meKey = ["auth", "me"] as const;

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

export function useRegisterMutation() {
  return useMutation({
    mutationFn: (payload: {
      email: string;
      password: string;
      full_name: string;
      phone_number?: string;
    }) => authApi.register(payload),
  });
}

export function useForgotPasswordMutation() {
  return useMutation({
    mutationFn: (email: string) => authApi.forgotPassword(email),
  });
}

export function useResetPasswordMutation() {
  return useMutation({
    mutationFn: ({ token, newPassword }: { token: string; newPassword: string }) =>
      authApi.resetPassword(token, newPassword),
  });
}

export function useVerifyEmailMutation() {
  return useMutation({
    mutationFn: (token: string) => authApi.verifyEmail(token),
  });
}

export function useCurrentUser() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return useQuery({
    queryKey: meKey,
    queryFn: () => authApi.me(),
    enabled: isAuthenticated,
  });
}

export function useChangePasswordMutation() {
  return useMutation({
    mutationFn: ({ currentPassword, newPassword }: { currentPassword: string; newPassword: string }) =>
      authApi.changePassword(currentPassword, newPassword),
  });
}

export function useSetupTwoFactorMutation() {
  return useMutation({
    mutationFn: () => authApi.setupTwoFactor(),
  });
}

export function useConfirmTwoFactorMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (otpCode: string) => authApi.confirmTwoFactor(otpCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: meKey }),
  });
}

export function useDisableTwoFactorMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (otpCode: string) => authApi.disableTwoFactor(otpCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: meKey }),
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
