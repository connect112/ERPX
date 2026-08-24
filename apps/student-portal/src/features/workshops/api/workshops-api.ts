import { apiClient } from "@/api/client";

export interface WorkshopPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  trainer_id: string | null;
  code: string;
  title: string;
  description: string | null;
  mode: "physical" | "virtual";
  venue: string | null;
  meeting_link: string | null;
  workshop_date: string;
  start_time: string;
  end_time: string;
  capacity: number | null;
  fee: number;
  status: "draft" | "published" | "ongoing" | "completed" | "cancelled";
  created_at: string;
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

export const workshopsApi = {
  browse: () => apiClient.get<WorkshopPublic[]>("/workshops/me").then((r) => r.data),

  myRegistrations: () =>
    apiClient.get<WorkshopRegistrationPublic[]>("/workshops/me/registrations").then((r) => r.data),

  register: (workshopId: string) =>
    apiClient
      .post<WorkshopRegistrationPublic>(`/workshops/${workshopId}/register/me`)
      .then((r) => r.data),
};
