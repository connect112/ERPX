import { apiClient } from "@/api/client";
import type { WorkshopMode, WorkshopStatus } from "@/features/workshops/schemas/workshop-schemas";

export interface WorkshopPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  trainer_id: string | null;
  code: string;
  title: string;
  description: string | null;
  mode: WorkshopMode;
  venue: string | null;
  meeting_link: string | null;
  workshop_date: string;
  start_time: string;
  end_time: string;
  capacity: number | null;
  fee: number;
  status: WorkshopStatus;
  created_at: string;
}

export interface WorkshopListResponse {
  items: WorkshopPublic[];
  total: number;
}

export interface WorkshopListParams {
  status?: WorkshopStatus;
  upcoming_only?: boolean;
  skip?: number;
  limit?: number;
}

export interface WorkshopCreatePayload {
  code: string;
  title: string;
  description?: string;
  branch_id?: string;
  trainer_id?: string;
  mode: WorkshopMode;
  venue?: string;
  meeting_link?: string;
  workshop_date: string;
  start_time: string;
  end_time: string;
  capacity?: number;
  fee?: number;
}

export interface WorkshopUpdatePayload {
  title?: string;
  description?: string;
  trainer_id?: string;
  mode?: WorkshopMode;
  venue?: string;
  meeting_link?: string;
  workshop_date?: string;
  start_time?: string;
  end_time?: string;
  capacity?: number;
  fee?: number;
}

export interface WorkshopRegistrationPublic {
  id: string;
  workshop_id: string;
  student_id: string | null;
  contact_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  registered_at: string;
  status: "registered" | "attended" | "no_show" | "cancelled";
  is_paid: boolean;
  created_at: string;
}

export interface RegistrationCreatePayload {
  student_id?: string;
  contact_name: string;
  contact_email?: string;
  contact_phone?: string;
}

export const workshopsApi = {
  list: (params: WorkshopListParams) =>
    apiClient.get<WorkshopListResponse>("/workshops", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<WorkshopPublic>(`/workshops/${id}`).then((r) => r.data),

  create: (payload: WorkshopCreatePayload) =>
    apiClient.post<WorkshopPublic>("/workshops", payload).then((r) => r.data),

  update: (id: string, payload: WorkshopUpdatePayload) =>
    apiClient.patch<WorkshopPublic>(`/workshops/${id}`, payload).then((r) => r.data),

  changeStatus: (id: string, status: WorkshopStatus) =>
    apiClient.post<WorkshopPublic>(`/workshops/${id}/status`, { status }).then((r) => r.data),

  delete: (id: string) => apiClient.delete(`/workshops/${id}`).then((r) => r.data),

  listRegistrations: (id: string) =>
    apiClient.get<WorkshopRegistrationPublic[]>(`/workshops/${id}/registrations`).then((r) => r.data),

  createRegistration: (id: string, payload: RegistrationCreatePayload) =>
    apiClient
      .post<WorkshopRegistrationPublic>(`/workshops/${id}/registrations`, payload)
      .then((r) => r.data),

  markAttendance: (registrationId: string, attended: boolean) =>
    apiClient
      .post<WorkshopRegistrationPublic>(`/workshops/registrations/${registrationId}/attendance`, {
        attended,
      })
      .then((r) => r.data),

  cancelRegistration: (registrationId: string) =>
    apiClient
      .post<WorkshopRegistrationPublic>(`/workshops/registrations/${registrationId}/cancel`)
      .then((r) => r.data),
};
