import { apiClient } from "@/api/client";

export interface PermissionPublic {
  id: string;
  code: string;
  module: string;
  description: string | null;
}

export interface RolePublic {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_system: boolean;
  created_at: string;
}

export interface RoleWithPermissions extends RolePublic {
  permissions: PermissionPublic[];
}

export interface RoleCreatePayload {
  name: string;
  slug: string;
  description?: string;
}

export interface RoleUpdatePayload {
  name?: string;
  description?: string;
}

export interface UserRolesResponse {
  user_id: string;
  roles: RolePublic[];
  effective_permissions: string[];
}

export const authorizationApi = {
  listPermissions: () =>
    apiClient.get<PermissionPublic[]>("/authorization/permissions").then((r) => r.data),

  listRoles: () => apiClient.get<RolePublic[]>("/authorization/roles").then((r) => r.data),

  getRole: (id: string) =>
    apiClient.get<RoleWithPermissions>(`/authorization/roles/${id}`).then((r) => r.data),

  createRole: (payload: RoleCreatePayload) =>
    apiClient.post<RolePublic>("/authorization/roles", payload).then((r) => r.data),

  updateRole: (id: string, payload: RoleUpdatePayload) =>
    apiClient.patch<RolePublic>(`/authorization/roles/${id}`, payload).then((r) => r.data),

  deleteRole: (id: string) => apiClient.delete(`/authorization/roles/${id}`).then((r) => r.data),

  setRolePermissions: (id: string, permissionCodes: string[]) =>
    apiClient
      .put<RoleWithPermissions>(`/authorization/roles/${id}/permissions`, { permission_codes: permissionCodes })
      .then((r) => r.data),

  assignRole: (userId: string, roleId: string) =>
    apiClient
      .post("/authorization/user-roles", { user_id: userId, role_id: roleId })
      .then((r) => r.data as { message: string }),

  revokeRole: (userId: string, roleId: string) =>
    apiClient
      .delete("/authorization/user-roles", { data: { user_id: userId, role_id: roleId } })
      .then((r) => r.data as { message: string }),

  getUserRoles: (userId: string) =>
    apiClient.get<UserRolesResponse>(`/authorization/users/${userId}/roles`).then((r) => r.data),
};
