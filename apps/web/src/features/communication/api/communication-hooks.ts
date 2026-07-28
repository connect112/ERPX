import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type SendCommunicationPayload,
  communicationApi,
} from "@/features/communication/api/communication-api";
import type { Channel, CommunicationStatus } from "@/features/communication/schemas/communication-schemas";

const communicationKeys = {
  all: ["communication"] as const,
  logs: (params: { channel?: Channel; status?: CommunicationStatus; skip?: number; limit?: number }) =>
    [...communicationKeys.all, "logs", params] as const,
};

export function useCommunicationLogs(params: {
  channel?: Channel;
  status?: CommunicationStatus;
  skip?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: communicationKeys.logs(params),
    queryFn: () => communicationApi.listLogs(params),
    placeholderData: keepPreviousData,
  });
}

export function useSendCommunication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SendCommunicationPayload) => communicationApi.send(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: communicationKeys.all }),
  });
}
