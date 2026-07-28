import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuthStore } from "@/store/auth-store";
import {
  type RegisterUserPayload,
  type UserListParams,
  type UserProfileCreatePayload,
  type UserProfileUpdatePayload,
  usersApi,
} from "@/features/users/api/users-api";

const usersKeys = {
  all: ["users"] as const,
  list: (params: UserListParams) => [...usersKeys.all, "list", params] as const,
  profile: (userId: string) => [...usersKeys.all, "profile", userId] as const,
};

export function useUsersList(params: UserListParams) {
  return useQuery({
    queryKey: usersKeys.list(params),
    queryFn: () => usersApi.list(params),
    enabled: !!params.organization_id,
    placeholderData: keepPreviousData,
  });
}

export function useUserProfile(userId: string | undefined) {
  return useQuery({
    queryKey: usersKeys.profile(userId ?? ""),
    queryFn: () => usersApi.getProfile(userId as string),
    enabled: !!userId,
  });
}

export function useCurrentUserProfile() {
  const currentUserId = useAuthStore((state) => state.user?.id);
  return useQuery({
    queryKey: usersKeys.profile(currentUserId ?? ""),
    queryFn: () => usersApi.getProfile(currentUserId as string),
    enabled: !!currentUserId,
    retry: false,
  });
}

export function useRegisterUser() {
  return useMutation({
    mutationFn: (payload: RegisterUserPayload) => usersApi.registerUser(payload),
  });
}

export function useCreateUserProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserProfileCreatePayload) => usersApi.createProfile(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usersKeys.all }),
  });
}

export function useUpdateUserProfile(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserProfileUpdatePayload) => usersApi.updateProfile(userId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usersKeys.all }),
  });
}
