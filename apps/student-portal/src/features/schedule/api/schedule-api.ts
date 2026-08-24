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

export interface LiveClassPublic {
  id: string;
  organization_id: string;
  batch_id: string;
  trainer_id: string | null;
  title: string;
  scheduled_at: string;
  duration_minutes: number;
  meeting_link: string;
  recording_url: string | null;
  status: "scheduled" | "live" | "completed" | "cancelled";
  created_at: string;
}

export const scheduleApi = {
  myTimetable: () => apiClient.get<TimetableEntryPublic[]>("/timetable/me").then((r) => r.data),

  myLiveClasses: () => apiClient.get<LiveClassPublic[]>("/live-classes/me").then((r) => r.data),
};
