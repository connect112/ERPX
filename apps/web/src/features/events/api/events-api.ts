import { apiClient } from "@/api/client";
import type { EventType } from "@/features/events/schemas/event-schemas";

export interface EventPublic {
  id: string;
  organization_id: string;
  created_by_user_id: string | null;
  title: string;
  description: string | null;
  event_type: EventType;
  start_at: string;
  end_at: string | null;
  location: string | null;
  is_all_day: boolean;
  created_at: string;
}

export interface EventListResponse {
  items: EventPublic[];
  total: number;
}

export interface EventListParams {
  event_type?: EventType;
  skip?: number;
  limit?: number;
}

export interface EventCreatePayload {
  title: string;
  description?: string;
  event_type: EventType;
  start_at: string;
  end_at?: string;
  location?: string;
  is_all_day: boolean;
}

export type EventUpdatePayload = Partial<EventCreatePayload>;

export const eventsApi = {
  list: (params: EventListParams) =>
    apiClient.get<EventListResponse>("/events", { params }).then((r) => r.data),

  create: (payload: EventCreatePayload) =>
    apiClient.post<EventPublic>("/events", payload).then((r) => r.data),

  update: (id: string, payload: EventUpdatePayload) =>
    apiClient.patch<EventPublic>(`/events/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/events/${id}`).then((r) => r.data),
};
