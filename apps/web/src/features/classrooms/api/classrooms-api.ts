import { apiClient } from "@/api/client";

export type ClassroomType = "physical" | "virtual";

export interface ClassroomPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  name: string;
  code: string;
  classroom_type: ClassroomType;
  capacity: number | null;
  location: string | null;
  meeting_link: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ClassroomListResponse {
  items: ClassroomPublic[];
  total: number;
}

export interface ClassroomCreatePayload {
  branch_id?: string;
  name: string;
  code: string;
  classroom_type: ClassroomType;
  capacity?: number;
  location?: string;
  meeting_link?: string;
}

export type ClassroomUpdatePayload = Partial<Omit<ClassroomCreatePayload, "code">> & {
  is_active?: boolean;
};

export const classroomsApi = {
  list: (params: { skip?: number; limit?: number }) =>
    apiClient.get<ClassroomListResponse>("/classrooms", { params }).then((r) => r.data),

  create: (payload: ClassroomCreatePayload) =>
    apiClient.post<ClassroomPublic>("/classrooms", payload).then((r) => r.data),

  update: (id: string, payload: ClassroomUpdatePayload) =>
    apiClient.patch<ClassroomPublic>(`/classrooms/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/classrooms/${id}`).then((r) => r.data),
};
