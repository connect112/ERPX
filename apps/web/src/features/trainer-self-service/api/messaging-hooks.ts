import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { myMessagingApi } from "@/features/trainer-self-service/api/messaging-api";

const myMessagingKeys = {
  all: ["messaging", "trainer", "me"] as const,
  students: () => [...myMessagingKeys.all, "students"] as const,
  conversations: () => [...myMessagingKeys.all, "conversations"] as const,
  unreadCount: () => [...myMessagingKeys.all, "unread-count"] as const,
  messages: (conversationId: string) => [...myMessagingKeys.all, "messages", conversationId] as const,
};

export function useMyStudents() {
  return useQuery({
    queryKey: myMessagingKeys.students(),
    queryFn: () => myMessagingApi.listStudents(),
  });
}

export function useMyConversations() {
  return useQuery({
    queryKey: myMessagingKeys.conversations(),
    queryFn: () => myMessagingApi.listConversations(),
  });
}

export function useMyMessagingUnreadCount() {
  return useQuery({
    queryKey: myMessagingKeys.unreadCount(),
    queryFn: () => myMessagingApi.unreadCount(),
    refetchInterval: 30_000,
  });
}

export function useOpenConversationWithStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (studentId: string) => myMessagingApi.openConversationWithStudent(studentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: myMessagingKeys.conversations() }),
  });
}

export function useConversationMessages(conversationId: string | undefined) {
  return useQuery({
    queryKey: myMessagingKeys.messages(conversationId ?? ""),
    queryFn: () => myMessagingApi.listMessages(conversationId as string),
    enabled: !!conversationId,
  });
}

export function useSendMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { body: string | null; attachment?: File }) => {
      let attachmentDocumentId: string | undefined;
      if (input.attachment) {
        const { document_id, upload_url } = await myMessagingApi.requestAttachmentUpload(
          input.attachment.name,
          input.attachment.type || "application/octet-stream"
        );
        const uploadResponse = await myMessagingApi.uploadToPresignedUrl(upload_url, input.attachment);
        if (!uploadResponse.ok) {
          throw new Error("Attachment upload failed.");
        }
        await myMessagingApi.confirmAttachmentUpload(document_id);
        attachmentDocumentId = document_id;
      }
      return myMessagingApi.sendMessage(conversationId, input.body, attachmentDocumentId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: myMessagingKeys.messages(conversationId) });
      queryClient.invalidateQueries({ queryKey: myMessagingKeys.conversations() });
      queryClient.invalidateQueries({ queryKey: myMessagingKeys.unreadCount() });
    },
  });
}
