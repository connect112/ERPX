import { apiClient } from "@/api/client";
import type { Channel, CommunicationStatus } from "@/features/communication/schemas/communication-schemas";

export interface CommunicationLogPublic {
  id: string;
  organization_id: string;
  channel: Channel;
  recipient: string;
  subject: string | null;
  body: string;
  status: CommunicationStatus;
  error_message: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
  sent_by_user_id: string | null;
  sent_at: string;
  created_at: string;
}

export interface CommunicationLogListResponse {
  items: CommunicationLogPublic[];
  total: number;
}

export interface SendCommunicationPayload {
  channel: Channel;
  recipient: string;
  subject?: string;
  body: string;
}

export const communicationApi = {
  send: (payload: SendCommunicationPayload) =>
    apiClient.post<CommunicationLogPublic>("/communication/send", payload).then((r) => r.data),

  listLogs: (params: { channel?: Channel; status?: CommunicationStatus; skip?: number; limit?: number }) =>
    apiClient.get<CommunicationLogListResponse>("/communication/logs", { params }).then((r) => r.data),
};
