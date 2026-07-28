import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bookmarksApi } from "@/features/bookmarks/api/bookmarks-api";

const bookmarksKey = ["bookmarks", "me"] as const;

export function useMyBookmarks() {
  return useQuery({
    queryKey: bookmarksKey,
    queryFn: () => bookmarksApi.myBookmarks(),
  });
}

export function useAddBookmark() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lessonId: string) => bookmarksApi.addBookmark(lessonId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookmarksKey }),
  });
}

export function useRemoveBookmark() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lessonId: string) => bookmarksApi.removeBookmark(lessonId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: bookmarksKey }),
  });
}
