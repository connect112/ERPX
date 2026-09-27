import { apiClient } from "@/api/client";

export interface TrainerContact {
  trainer_id: string;
  full_name: string;
}

export interface MessagePublic {
  id: string;
  conversation_id: string;
  sender_user_id: string | null;
  body: string | null;
  attachment_document_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface ConversationPublic {
  id: string;
  student_id: string;
  trainer_id: string;
  counterpart_name: string;
  last_message: MessagePublic | null;
  unread_count: number;
  created_at: string;
}

export const messagingApi = {
  // Ownership-gated via get_current_student (modules/messaging/routes.py)
  // -- no permission code, works for any linked student. Only trainers
  // actually teaching a batch this student is enrolled in show up here.
  listTrainers: () => apiClient.get<TrainerContact[]>("/messaging/me/trainers").then((r) => r.data),

  listConversations: () =>
    apiClient
      .get<{ items: ConversationPublic[] }>("/messaging/me/conversations")
      .then((r) => r.data.items),

  unreadCount: () =>
    apiClient
      .get<{ unread_count: number }>("/messaging/me/conversations/unread-count")
      .then((r) => r.data.unread_count),

  openConversationWithTrainer: (trainerId: string) =>
    apiClient
      .post<{ id: string }>(`/messaging/me/conversations/with/${trainerId}`)
      .then((r) => r.data),

  listMessages: (conversationId: string) =>
    apiClient
      .get<MessagePublic[]>(`/messaging/me/conversations/${conversationId}/messages`)
      .then((r) => r.data),

  sendMessage: (conversationId: string, body: string | null, attachmentDocumentId?: string) =>
    apiClient
      .post<MessagePublic>(`/messaging/me/conversations/${conversationId}/messages`, {
        body,
        attachment_document_id: attachmentDocumentId,
      })
      .then((r) => r.data),

  requestAttachmentUpload: (filename: string, contentType: string) =>
    apiClient
      .post<{ document_id: string; upload_url: string }>("/messaging/me/attachments/presigned-upload", {
        filename,
        content_type: contentType,
      })
      .then((r) => r.data),

  // Goes straight to MinIO's presigned URL, not through apiClient -- this
  // isn't an ERPX API route, and needs no auth header of its own.
  uploadToPresignedUrl: (uploadUrl: string, file: File) =>
    fetch(uploadUrl, {
      method: "PUT",
      body: file,
      headers: { "Content-Type": file.type || "application/octet-stream" },
    }),

  confirmAttachmentUpload: (documentId: string) =>
    apiClient.post(`/messaging/me/attachments/${documentId}/confirm`).then((r) => r.data),
};
