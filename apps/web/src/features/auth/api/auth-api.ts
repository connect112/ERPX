import { apiClient } from "@/api/client";

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  phone_number: string | null;
  status: "pending_verification" | "active" | "suspended" | "deactivated";
  is_email_verified: boolean;
  two_factor_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserPublic;
}

export interface TwoFactorRequiredResponse {
  two_factor_required: true;
}

export type LoginResponse = TokenResponse | TwoFactorRequiredResponse;

export function isTwoFactorRequired(
  response: LoginResponse
): response is TwoFactorRequiredResponse {
  return "two_factor_required" in response;
}

export const authApi = {
  register: (payload: {
    email: string;
    password: string;
    full_name: string;
    phone_number?: string;
  }) => apiClient.post<UserPublic>("/auth/register", payload).then((r) => r.data),

  login: (payload: { email: string; password: string; otp_code?: string }) =>
    apiClient.post<LoginResponse>("/auth/login", payload).then((r) => r.data),

  refresh: (refresh_token: string) =>
    apiClient
      .post<Omit<TokenResponse, "user">>("/auth/refresh", { refresh_token })
      .then((r) => r.data),

  logout: (refresh_token: string) =>
    apiClient.post("/auth/logout", { refresh_token }).then((r) => r.data),

  me: () => apiClient.get<UserPublic>("/auth/me").then((r) => r.data),

  verifyEmail: (token: string) =>
    apiClient.post("/auth/verify-email", { token }).then((r) => r.data),

  resendVerification: (email: string) =>
    apiClient.post("/auth/resend-verification", { email }).then((r) => r.data),

  forgotPassword: (email: string) =>
    apiClient.post("/auth/forgot-password", { email }).then((r) => r.data),

  resetPassword: (token: string, new_password: string) =>
    apiClient.post("/auth/reset-password", { token, new_password }).then((r) => r.data),

  changePassword: (current_password: string, new_password: string) =>
    apiClient
      .post("/auth/change-password", { current_password, new_password })
      .then((r) => r.data),

  setupTwoFactor: () =>
    apiClient
      .post<{ secret: string; otpauth_url: string; qr_code_base64: string }>("/auth/2fa/setup")
      .then((r) => r.data),

  confirmTwoFactor: (otp_code: string) =>
    apiClient.post("/auth/2fa/confirm", { otp_code }).then((r) => r.data),

  disableTwoFactor: (otp_code: string) =>
    apiClient.post("/auth/2fa/disable", { otp_code }).then((r) => r.data),
};
