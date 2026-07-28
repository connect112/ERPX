import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type RoleCreatePayload,
  type RoleUpdatePayload,
  authorizationApi,
} from "@/features/authorization/api/authorization-api";

const permissionsKey = ["authorization", "permissions"] as const;
const rolesKeys = {
  all: ["authorization", "roles"] as const,
  detail: (id: string) => [...rolesKeys.all, "detail", id] as const,
};
const userRolesKey = (userId: string) => ["authorization", "user-roles", userId] as const;

export function usePermissions() {
  return useQuery({
    queryKey: permissionsKey,
    queryFn: () => authorizationApi.listPermissions(),
  });
}

export function useRolesList() {
  return useQuery({
    queryKey: rolesKeys.all,
    queryFn: () => authorizationApi.listRoles(),
  });
}

export function useRole(id: string | undefined) {
  return useQuery({
    queryKey: rolesKeys.detail(id ?? ""),
    queryFn: () => authorizationApi.getRole(id as string),
    enabled: !!id,
  });
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RoleCreatePayload) => authorizationApi.createRole(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: rolesKeys.all }),
  });
}

export function useUpdateRole(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RoleUpdatePayload) => authorizationApi.updateRole(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: rolesKeys.all }),
  });
}

export function useDeleteRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => authorizationApi.deleteRole(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: rolesKeys.all }),
  });
}

export function useSetRolePermissions(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (permissionCodes: string[]) => authorizationApi.setRolePermissions(id, permissionCodes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: rolesKeys.detail(id) }),
  });
}

export function useUserRoles(userId: string | undefined) {
  return useQuery({
    queryKey: userRolesKey(userId ?? ""),
    queryFn: () => authorizationApi.getUserRoles(userId as string),
    enabled: !!userId,
  });
}

export function useAssignRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) =>
      authorizationApi.assignRole(userId, roleId),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({ queryKey: userRolesKey(variables.userId) }),
  });
}

export function useRevokeRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) =>
      authorizationApi.revokeRole(userId, roleId),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({ queryKey: userRolesKey(variables.userId) }),
  });
}
