import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { discussionsApi } from "@/features/lms/discussions/api/discussions-api";

const threadsKey = (courseId: string) => ["lms", "discussions", courseId] as const;
const repliesKey = (courseId: string, threadId: string) =>
  [...threadsKey(courseId), threadId, "replies"] as const;

export function useThreads(courseId: string) {
  return useQuery({
    queryKey: threadsKey(courseId),
    queryFn: () => discussionsApi.listThreads(courseId),
    enabled: !!courseId,
  });
}

export function useCreateThread(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { title: string; body: string }) =>
      discussionsApi.createThread(courseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: threadsKey(courseId) }),
  });
}

export function useReplies(courseId: string, threadId: string) {
  return useQuery({
    queryKey: repliesKey(courseId, threadId),
    queryFn: () => discussionsApi.listReplies(courseId, threadId),
    enabled: !!courseId && !!threadId,
  });
}

export function useCreateReply(courseId: string, threadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => discussionsApi.reply(courseId, threadId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: repliesKey(courseId, threadId) }),
  });
}
