import { apiClient } from "@/api/client";

export interface TrainerPublic {
  id: string;
  organization_id: string;
  employee_id: string;
  employee_name: string;
  employee_email: string | null;
  specializations: string | null;
  bio: string | null;
  max_weekly_hours: number | null;
  is_active: boolean;
  created_at: string;
}

export const trainerApi = {
  me: () => apiClient.get<TrainerPublic>("/trainers/me").then((r) => r.data),
};
