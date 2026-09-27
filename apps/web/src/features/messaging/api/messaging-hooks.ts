import { keepPreviousData, useQuery } from "@tanstack/react-query";

import {
  type AdminConversationListParams,
  messagingApi,
} from "@/features/messaging/api/messaging-api";

const messagingKeys = {
  all: ["messaging", "admin"] as const,
  list: (params: AdminConversationListParams) => [...messagingKeys.all, "list", params] as const,
  messages: (conversationId: string) => [...messagingKeys.all, "messages", conversationId] as const,
};

export function useAdminConversationsList(params: AdminConversationListParams) {
  return useQuery({
    queryKey: messagingKeys.list(params),
    queryFn: () => messagingApi.listConversations(params),
    placeholderData: keepPreviousData,
  });
}

export function useAdminConversationMessages(conversationId: string | undefined) {
  return useQuery({
    queryKey: messagingKeys.messages(conversationId ?? ""),
    queryFn: () => messagingApi.listMessages(conversationId as string),
    enabled: !!conversationId,
  });
}
