import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { myLiveClassesApi } from "@/features/trainer-self-service/api/live-classes-api";
import type { LiveClassStatus } from "@/features/live-classes/api/live-classes-api";

const myLiveClassesKey = ["live-classes", "trainer", "me"] as const;

export function useMyLiveClasses() {
  return useQuery({
    queryKey: myLiveClassesKey,
    queryFn: () => myLiveClassesApi.myLiveClasses(),
  });
}

export function useChangeMyLiveClassStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      recordingUrl,
    }: {
      id: string;
      status: LiveClassStatus;
      recordingUrl?: string;
    }) => myLiveClassesApi.changeStatus(id, { status, recording_url: recordingUrl }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: myLiveClassesKey }),
  });
}

export function useJoinMyLiveClass() {
  return useMutation({
    mutationFn: (id: string) => myLiveClassesApi.joinToken(id),
  });
}
