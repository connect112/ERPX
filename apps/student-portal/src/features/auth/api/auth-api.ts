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
  login: (payload: { email: string; password: string; otp_code?: string }) =>
    apiClient.post<LoginResponse>("/auth/login", payload).then((r) => r.data),

  logout: (refresh_token: string) =>
    apiClient.post("/auth/logout", { refresh_token }).then((r) => r.data),

  me: () => apiClient.get<UserPublic>("/auth/me").then((r) => r.data),
};
