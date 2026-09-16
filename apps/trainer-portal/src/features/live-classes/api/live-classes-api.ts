import { apiClient } from "@/api/client";

export type LiveClassStatus = "scheduled" | "live" | "completed" | "cancelled";

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
  status: LiveClassStatus;
  created_at: string;
}

export interface LiveClassJoinToken {
  domain: string;
  room: string;
  jwt: string;
}

export const liveClassesApi = {
  // Ownership-gated (see modules/live_classes/routes.py's
  // list_my_live_classes_as_trainer) — every live class scheduled for a
  // batch this trainer teaches, not just ones with trainer_id set to them
  // specifically.
  myLiveClasses: () => apiClient.get<LiveClassPublic[]>("/live-classes/trainer/me").then((r) => r.data),

  changeStatus: (id: string, payload: { status: LiveClassStatus; recording_url?: string }) =>
    apiClient
      .post<LiveClassPublic>(`/live-classes/trainer/${id}/status`, payload)
      .then((r) => r.data),

  // A fresh, short-lived Jitsi JWT (moderator access) for the embedded
  // call — see modules/live_classes/jitsi.py. Minted per-join, not cached.
  joinToken: (id: string) =>
    apiClient
      .post<LiveClassJoinToken>(`/live-classes/trainer/${id}/join-token`)
      .then((r) => r.data),
};
