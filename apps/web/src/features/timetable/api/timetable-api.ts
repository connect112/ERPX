import { apiClient } from "@/api/client";

export type DayOfWeek =
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday"
  | "saturday"
  | "sunday";

export interface TimetableEntryPublic {
  id: string;
  organization_id: string;
  batch_id: string;
  classroom_id: string | null;
  trainer_id: string | null;
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  subject: string | null;
  created_at: string;
}

export interface TimetableEntryCreatePayload {
  batch_id: string;
  classroom_id?: string;
  trainer_id?: string;
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  subject?: string;
}

export const timetableApi = {
  listForBatch: (batchId: string) =>
    apiClient
      .get<TimetableEntryPublic[]>("/timetable", { params: { batch_id: batchId } })
      .then((r) => r.data),

  create: (payload: TimetableEntryCreatePayload) =>
    apiClient.post<TimetableEntryPublic>("/timetable", payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/timetable/${id}`).then((r) => r.data),
};
