import { apiClient } from "@/api/client";
import type { Gender, UserStatus } from "@/features/users/schemas/user-schemas";

export interface UserProfilePublic {
  id: string;
  user_id: string;
  organization_id: string;
  branch_id: string | null;
  employee_code: string | null;
  designation: string | null;
  department: string | null;
  avatar_url: string | null;
  gender: Gender | null;
  date_of_birth: string | null;
  date_of_joining: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  created_at: string;
}

export interface UserWithProfilePublic {
  id: string;
  email: string;
  full_name: string;
  status: UserStatus;
  is_email_verified: boolean;
  profile: UserProfilePublic | null;
}

export interface UserListParams {
  organization_id: string;
  skip?: number;
  limit?: number;
}

export interface RegisterUserPayload {
  email: string;
  password: string;
  full_name: string;
  phone_number?: string;
}

export interface UserProfileCreatePayload {
  user_id: string;
  organization_id: string;
  branch_id?: string;
  employee_code?: string;
  designation?: string;
  department?: string;
  gender?: Gender;
  date_of_birth?: string;
  date_of_joining?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
}

export interface UserProfileUpdatePayload {
  branch_id?: string;
  employee_code?: string;
  designation?: string;
  department?: string;
  gender?: Gender;
  date_of_birth?: string;
  date_of_joining?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
}

export const usersApi = {
  list: (params: UserListParams) =>
    apiClient.get<UserWithProfilePublic[]>("/users", { params }).then((r) => r.data),

  getProfile: (userId: string) =>
    apiClient.get<UserProfilePublic>(`/users/profiles/${userId}`).then((r) => r.data),

  registerUser: (payload: RegisterUserPayload) =>
    apiClient.post("/auth/register", payload).then((r) => r.data as { id: string }),

  createProfile: (payload: UserProfileCreatePayload) =>
    apiClient.post<UserProfilePublic>("/users/profiles", payload).then((r) => r.data),

  updateProfile: (userId: string, payload: UserProfileUpdatePayload) =>
    apiClient.patch<UserProfilePublic>(`/users/profiles/${userId}`, payload).then((r) => r.data),
};
