import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { messagingApi } from "@/features/messaging/api/messaging-api";

const messagingKeys = {
  all: ["messaging"] as const,
  students: () => [...messagingKeys.all, "students"] as const,
  conversations: () => [...messagingKeys.all, "conversations"] as const,
  unreadCount: () => [...messagingKeys.all, "unread-count"] as const,
  messages: (conversationId: string) => [...messagingKeys.all, "messages", conversationId] as const,
};

export function useMyStudents() {
  return useQuery({
    queryKey: messagingKeys.students(),
    queryFn: () => messagingApi.listStudents(),
  });
}

export function useMyConversations() {
  return useQuery({
    queryKey: messagingKeys.conversations(),
    queryFn: () => messagingApi.listConversations(),
  });
}

export function useMessagingUnreadCount() {
  return useQuery({
    queryKey: messagingKeys.unreadCount(),
    queryFn: () => messagingApi.unreadCount(),
    refetchInterval: 30_000,
  });
}

export function useOpenConversationWithStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (studentId: string) => messagingApi.openConversationWithStudent(studentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: messagingKeys.conversations() }),
  });
}

export function useConversationMessages(conversationId: string | undefined) {
  return useQuery({
    queryKey: messagingKeys.messages(conversationId ?? ""),
    queryFn: () => messagingApi.listMessages(conversationId as string),
    enabled: !!conversationId,
  });
}

export function useSendMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { body: string | null; attachment?: File }) => {
      let attachmentDocumentId: string | undefined;
      if (input.attachment) {
        const { document_id, upload_url } = await messagingApi.requestAttachmentUpload(
          input.attachment.name,
          input.attachment.type || "application/octet-stream"
        );
        const uploadResponse = await messagingApi.uploadToPresignedUrl(upload_url, input.attachment);
        if (!uploadResponse.ok) {
          throw new Error("Attachment upload failed.");
        }
        await messagingApi.confirmAttachmentUpload(document_id);
        attachmentDocumentId = document_id;
      }
      return messagingApi.sendMessage(conversationId, input.body, attachmentDocumentId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: messagingKeys.messages(conversationId) });
      queryClient.invalidateQueries({ queryKey: messagingKeys.conversations() });
      queryClient.invalidateQueries({ queryKey: messagingKeys.unreadCount() });
    },
  });
}
