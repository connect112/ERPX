import { apiClient } from "@/api/client";

export interface MessagePublic {
  id: string;
  conversation_id: string;
  sender_user_id: string | null;
  body: string | null;
  attachment_document_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface AdminConversationPublic {
  id: string;
  student_id: string;
  student_name: string;
  trainer_id: string;
  trainer_name: string;
  last_message: MessagePublic | null;
  created_at: string;
}

export interface AdminConversationListParams {
  student_id?: string;
  trainer_id?: string;
  skip?: number;
  limit?: number;
}

export interface AdminConversationListResponse {
  items: AdminConversationPublic[];
  total: number;
  skip: number;
  limit: number;
}

export const messagingApi = {
  // Read-only audit view -- gated by messaging.view_all
  // (modules/messaging/routes.py). There is deliberately no send route
  // here: admin can see every student-trainer conversation but not post
  // into one.
  listConversations: (params: AdminConversationListParams) =>
    apiClient.get<AdminConversationListResponse>("/messaging/conversations", { params }).then((r) => r.data),

  listMessages: (conversationId: string) =>
    apiClient.get<MessagePublic[]>(`/messaging/conversations/${conversationId}/messages`).then((r) => r.data),
};
