/**
 * Global auth store (Zustand).
 *
 * Holds the current access/refresh tokens and authenticated user profile.
 * The Authentication module's login/logout flows (built next) write to
 * this store; the Axios client and route guards read from it.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  status: "pending_verification" | "active" | "suspended" | "deactivated";
  isEmailVerified: boolean;
  twoFactorEnabled: boolean;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  /**
   * The logged-in user's effective permission codes (GET /authorization/me,
   * fetched once on login — see features/auth/api/auth-hooks.ts). Drives
   * which nav items and routes render (layouts/app-layout.tsx,
   * router/protected-route.tsx) — never hardcoded, so a role's actual
   * grant set on the server is always the single source of truth for what
   * the SPA shell shows, including for any future broader role tier.
   */
  permissions: string[];
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: AuthUser) => void;
  setPermissions: (permissions: string[]) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      permissions: [],
      setTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken, isAuthenticated: true }),
      setUser: (user) => set({ user }),
      setPermissions: (permissions) => set({ permissions }),
      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
          permissions: [],
        }),
    }),
    {
      name: "erpx-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        permissions: state.permissions,
      }),
    }
  )
);
