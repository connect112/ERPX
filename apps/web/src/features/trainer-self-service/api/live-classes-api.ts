import { apiClient } from "@/api/client";
import type { LiveClassPublic, LiveClassStatus } from "@/features/live-classes/api/live-classes-api";

export interface LiveClassJoinToken {
  domain: string;
  room: string;
  jwt: string;
}

export const myLiveClassesApi = {
  // Ownership-gated (see modules/live_classes/routes.py's
  // list_my_live_classes_as_trainer) — every live class scheduled for a
  // batch this trainer teaches, not just ones with trainer_id set to
  // them specifically.
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

  // Tells the backend the trainer has left the call -- re-locks the room
  // so a student trying to join afterward is told to wait rather than
  // walking into an empty one. Fire-and-forget from VideoCallOverlay's
  // videoConferenceLeft handler, not a user-facing action of its own.
  leave: (id: string) => apiClient.post(`/live-classes/trainer/${id}/leave`).then((r) => r.data),
};
